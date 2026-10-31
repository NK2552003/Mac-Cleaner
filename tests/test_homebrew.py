"""Homebrew graphs and mutations use synthetic receipts; no host packages change."""
import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from test_toolkit import wait_job

from mac_deep_cleaner.brew_cli import parser
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.homebrew import HomebrewManager, autoremove_names, build_graph, reverse_tree
from mac_deep_cleaner.system_tools import CommandRunner
from mac_deep_cleaner.toolkit import Toolkit


def formula(name, deps=(), requested=True, **extra):
    return {'name':name.split('/')[-1], 'full_name':name, 'tap':'homebrew/core',
            'desc':'Example ' + name, 'dependencies':list(deps), 'versions':{'stable':'2.0'},
            'installed':[{'version':'1.0','installed_on_request':requested,'poured_from_bottle':True,
                          'runtime_dependencies':[{'full_name':d,'declared_directly':True} for d in deps]}],
            'pinned':False,'outdated':False,**extra}


class FakeBrewRunner:
    def __init__(self):
        self.info = {'formulae':[
            formula('ffmpeg',['codec'],outdated=True), formula('git',['shared']),
            formula('codec',['shared'],False),formula('shared',requested=False),
            formula('unused',['orphan-lib'],False),formula('orphan-lib',requested=False),
            formula('pinned-lib',requested=False,pinned=True),
            formula('database',['db-lib'],False,service={'run':'postgres'}),
            formula('db-lib',requested=False),formula('mystery',requested=None)],
            'casks':[{'token':'studio','full_token':'studio','name':['Studio'],
                      'desc':'Video app','tap':'homebrew/cask','installed':'1.0','version':'1.0',
                      'depends_on':{'formula':['codec']}}]}
        self.services = [{'name':'database','status':'started'}]
        self.candidates = ['unused','orphan-lib','pinned-lib','database','db-lib']
        self.cleanup = 'Would remove: /opt/testbrew/cache/old-download (12 MB)'
        self.mutations = []
        self.fail_services = False
        self.fail_outdated = False
        self.hold = None

    def text(self, argv, timeout=20):
        args = argv[1:]
        if argv[0] == '/usr/bin/du':
            return '\n'.join(f'{(i+1)*1000}\t{path}' for i,path in enumerate(args[1:]))
        if args == ['--prefix']: return '/opt/testbrew'
        if args == ['--cellar']: return '/opt/testbrew/Cellar'
        if args == ['--caskroom']: return '/opt/testbrew/Caskroom'
        if args == ['info','--json=v2','--installed']: return json.dumps(self.info)
        if args == ['autoremove','--dry-run']:
            return f'==> Would autoremove {len(self.candidates)} unneeded formulae:\n'+'\n'.join(self.candidates) if self.candidates else ''
        if args == ['services','list','--json']:
            if self.fail_services: raise APIError(400,'services unavailable')
            return json.dumps(self.services)
        if args == ['outdated','--json=v2']:
            if self.fail_outdated: raise APIError(400,'outdated unavailable')
            return json.dumps({'formulae':[{'name':p['full_name'],'current_version':'2.0'} for p in self.info['formulae'] if p.get('outdated')], 'casks':[]})
        if args == ['cleanup','--dry-run']: return self.cleanup
        if args[:2] == ['upgrade','--dry-run']: return 'Would upgrade: ' + args[-1] + ' 1.0 -> 2.0\nWould install dependency: new-runtime'
        self.mutations.append(argv)
        if self.hold: self.hold.wait(2)
        if args[0] in ('pin','unpin'):
            next(p for p in self.info['formulae'] if p['full_name']==args[-1])['pinned'] = args[0]=='pin'
        elif args[0] == 'tab':
            p=next(p for p in self.info['formulae'] if p['full_name']==args[-1])
            p['installed'][0]['installed_on_request'] = args[1]=='--installed-on-request'
            if p['installed'][0]['installed_on_request'] and p['full_name'] in self.candidates:
                self.candidates.remove(p['full_name'])
        elif args[0] == 'uninstall':
            key='formulae' if args[1]=='--formula' else 'casks'
            self.info[key] = [p for p in self.info[key] if (p.get('full_name') or p.get('token')) not in args[2:]]
            self.candidates = [n for n in self.candidates if n not in args[2:]]
        elif args[0] == 'upgrade':
            p=next(p for p in self.info['formulae'] if p['full_name']==args[-1]);p['outdated']=False;p['installed'][0]['version']='2.0'
        return 'Completed fixture Homebrew command'


def manager(runner=None):
    return HomebrewManager(runner or FakeBrewRunner(), finder=lambda _: '/test/bin/brew')


class HomebrewGraphTest(unittest.TestCase):
    def setUp(self):
        self.runner=FakeBrewRunner(); self.manager=manager(self.runner)

    def test_requested_shared_cask_dependencies_and_orphan_chain(self):
        report=self.manager.report(); p={p['name']:p for p in report['packages']}
        self.assertEqual(report['stats']['total'],11)
        self.assertTrue(p['shared']['shared'])
        self.assertEqual(set(p['shared']['roots']),{'formula:git','formula:ffmpeg','cask:studio'})
        self.assertEqual({p['name'] for p in report['packages'] if p['orphan']},{'unused','orphan-lib'})
        self.assertEqual(p['mystery']['group'],'Unknown origin')
        self.assertFalse(p['pinned-lib']['orphan']);self.assertFalse(p['database']['orphan']);self.assertFalse(p['db-lib']['orphan'])
        self.assertEqual(self.runner.mutations,[])

    def test_receipt_dependencies_survive_metadata_changes(self):
        self.runner.info['formulae'][0]['dependencies']=[]
        p=self.manager.explain('shared')['package']
        self.assertIn('formula:ffmpeg',p['roots'])

    def test_unknown_receipt_or_service_state_disables_removal(self):
        for what in ('receipt','services','missing'):
            with self.subTest(what=what):
                r=FakeBrewRunner()
                if what=='receipt': del r.info['formulae'][0]['installed'][0]['runtime_dependencies']
                elif what=='services': r.fail_services=True
                else: r.info['formulae'][0]['installed'][0]['runtime_dependencies'].append({'full_name':'missing'})
                report=manager(r).report()
                self.assertFalse(report['removal_checks']);self.assertFalse(any(p['orphan'] for p in report['packages']))
                with self.assertRaises(APIError): manager(r).plan({'action':'uninstall','target':'git'})

    def test_aliases_taps_and_namespaces_are_not_conflated(self):
        self.runner.info['formulae'].append(formula('vendor/tap/lib',aliases=['old-lib']))
        self.runner.info['formulae'].append(formula('consumer',['old-lib']))
        self.runner.info['casks'].append({'token':'git','full_token':'git','installed':'1','depends_on':{}})
        report=self.manager.report()
        self.assertEqual(self.manager.resolve(report,'consumer')['dependencies'],['formula:vendor/tap/lib'])
        with self.assertRaises(APIError): self.manager.resolve(report,'git')
        self.assertEqual(self.manager.resolve(report,'formula:git')['kind'],'formula')
        self.assertEqual(self.manager.resolve(report,'cask:git')['kind'],'cask')

    def test_cycles_and_shared_reverse_branches_are_bounded(self):
        info={'formulae':[formula('a',['b']),formula('b',['a']),formula('c',['a','b'])],'casks':[]}
        packages,_,_=build_graph(info,[],[])
        tree=reverse_tree(packages,'formula:a')
        self.assertTrue(any(r['cycle'] for r in tree['rows']))
        self.assertLess(len(tree['rows']),8)
        self.assertTrue(reverse_tree(packages,'formula:a',limit=1)['truncated'])

    def test_autoremove_unknown_format_or_unlisted_candidates_fail_closed(self):
        self.assertEqual(autoremove_names(''),[])
        self.assertEqual(autoremove_names('==> Would autoremove 1 unneeded formula:\nabc'),['abc'])
        for output in ('Would remove all packages','==> Would autoremove 2 unneeded formulae:\nabc','==> Would autoremove 1 unneeded formula:\n--force'):
            with self.subTest(output=output),self.assertRaises(APIError): autoremove_names(output)
        self.runner.candidates.append('not-installed')
        self.assertFalse(self.manager.report()['removal_checks'])

    def test_brewfile_exports_roots_and_casks_with_no_shell_or_versions(self):
        output=self.manager.brewfile()
        self.assertIn('brew "ffmpeg"',output);self.assertIn('cask "studio"',output)
        self.assertIn('brew "mystery"',output);self.assertNotIn('brew "shared"',output)

    def test_not_installed_and_malformed_inventory(self):
        self.assertFalse(HomebrewManager(finder=lambda _:None).report()['available'])
        for bad in ({}, {'formulae':{},'casks':[]}):
            with self.assertRaises(APIError): build_graph(bad,[],[])


class HomebrewPlanTest(unittest.TestCase):
    def setUp(self):
        self.runner=FakeBrewRunner();self.toolkit=Toolkit(threading.Lock(),runner=self.runner)
        self.toolkit.brew=manager(self.runner)

    def plan(self,action,target=None): return self.toolkit.prepare('brew',{'action':action,'target':target})
    def start(self,plan): return self.toolkit.start({'token':plan['token'],'confirmed':True,'phrase':plan['phrase']})

    def test_tidy_uses_exact_reviewed_set_not_blanket_autoremove(self):
        plan=self.plan('tidy')
        self.assertEqual(plan['commands'],[['/test/bin/brew','uninstall','--formula','unused','orphan-lib']])
        self.assertFalse(self.runner.mutations)
        with self.assertRaises(APIError): self.toolkit.start({'token':plan['token'],'confirmed':True})
        self.start(plan);self.assertEqual(wait_job(self.toolkit)['status'],'succeeded')
        self.assertEqual(self.runner.mutations,plan['commands'])
        with self.assertRaises(APIError): self.start(plan)

    def test_required_pinned_and_service_packages_cannot_be_uninstalled(self):
        for name in ('shared','codec','pinned-lib','database','db-lib'):
            with self.subTest(name=name),self.assertRaises(APIError): self.plan('uninstall',name)
        self.assertFalse(self.runner.mutations)

    def test_changed_dependency_graph_is_rejected_before_execution(self):
        plan=self.plan('uninstall','git')
        self.runner.info['formulae'].append(formula('new-consumer',['git']))
        self.start(plan)
        self.assertEqual(wait_job(self.toolkit)['status'],'failed');self.assertFalse(self.runner.mutations)

    def test_changed_cleanup_preview_is_rejected(self):
        plan=self.plan('cleanup');self.runner.cleanup+='\nWould remove a newly downloaded cache'
        self.start(plan);self.assertEqual(wait_job(self.toolkit)['status'],'failed');self.assertFalse(self.runner.mutations)

    def test_upgrade_previews_dependencies_and_revalidates(self):
        plan=self.plan('upgrade','ffmpeg');self.assertIn('new-runtime',plan['preview'])
        self.start(plan);self.assertEqual(wait_job(self.toolkit)['status'],'succeeded')
        self.assertEqual(self.runner.mutations[-1],['/test/bin/brew','upgrade','--formula','ffmpeg'])
        self.assertFalse(self.toolkit.brew.report()['packages'][0]['outdated'])

    def test_keep_pin_services_and_input_validation(self):
        for action,target in [('keep','unused'),('pin','git'),('service-stop','database')]:
            plan=self.plan(action,target);self.start(plan);self.assertEqual(wait_job(self.toolkit)['status'],'succeeded')
        for target in ('--force','https://evil.test/pkg.rb','missing',[]):
            with self.subTest(target=target),self.assertRaises(APIError): self.plan('uninstall',target)
        with self.assertRaises(APIError): self.plan([],None)

    def test_failed_update_check_does_not_claim_no_updates(self):
        self.runner.fail_outdated=True
        self.assertFalse(self.toolkit.brew.report()['update_status'])
        with self.assertRaises(APIError):self.plan('upgrade','ffmpeg')

    def test_legacy_cleanup_preview_never_executes_mutations(self):
        plan=self.toolkit.prepare('tool',{'action':'brew-preview'})
        self.start(plan);job=wait_job(self.toolkit)
        self.assertEqual(job['status'],'succeeded');self.assertIn('Would remove:',job['output'])
        self.assertEqual(self.runner.mutations,[])


class HomebrewCLITest(unittest.TestCase):
    def test_reference_commands_are_namespaced_under_the_app(self):
        for command in ('dashboard','overview','heaviest','audit','stats','tidy','export'):
            self.assertEqual(parser().parse_args([command]).command,command)
        for command in ('explain','reverse-tree','upgrade','uninstall','keep'):
            self.assertEqual(parser().parse_args([command,'openssl@3']).package,'openssl@3')
        result=subprocess.run([sys.executable,'-m','mac_deep_cleaner','brew','--help'],capture_output=True,text=True,check=True)
        self.assertIn('reverse-tree',result.stdout)

    def test_runner_suppresses_unreviewed_cleanup_and_dependent_upgrades(self):
        with patch('mac_deep_cleaner.system_tools.IS_MAC',True),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,b'ok',b'')) as run:
            CommandRunner().run(['/test/bin/brew','upgrade','--formula','git'])
        env=run.call_args.kwargs['env']
        for key in ('HOMEBREW_NO_AUTOREMOVE','HOMEBREW_NO_INSTALL_CLEANUP','HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK','HOMEBREW_NO_AUTO_UPDATE'):
            self.assertEqual(env[key],'1')
