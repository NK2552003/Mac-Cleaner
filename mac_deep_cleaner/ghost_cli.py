"""Ghost Files CLI. Off/disable commands import only the core feature switch."""
import argparse
import json
import sys

from .errors import APIError
from .feature_config import MODEL_IDS, read_config, update_config


def consent(question, yes):
    print(question)
    return yes or (sys.stdin.isatty() and input('Continue? [y/N] ').strip().lower() == 'y')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='mdc ghosts', description='Opt-in, local app-leftover discovery.')
    commands = parser.add_subparsers(dest='command', required=True)
    enable = commands.add_parser('enable')
    enable.add_argument('--level', type=int, choices=(1, 2), default=1)
    enable.add_argument('--yes', action='store_true')
    enable.add_argument('--model', choices=MODEL_IDS)
    setup = commands.add_parser('setup')
    setup.add_argument('--model', choices=MODEL_IDS)
    setup.add_argument('--yes', action='store_true')
    scan = commands.add_parser('scan')
    scan.add_argument('--no-llm', action='store_true')
    scan.add_argument('--json', action='store_true')
    remove = commands.add_parser('remove-ai')
    remove.add_argument('--yes', action='store_true')
    commands.add_parser('disable')
    commands.add_parser('status')
    commands.add_parser('ofrenda')
    args = parser.parse_args(argv)
    try:
        if args.command == 'disable':
            update_config({'level': 0})
            print('Ghost Files is off. No AI components were removed.')
            return
        if args.command == 'status':
            print(json.dumps(read_config(), indent=2))
            return
        if args.command == 'enable':
            update_config({'level': args.level})
            if args.level == 1:
                print('Ghost Files enabled without AI. Run mdc ghosts scan or open Settings in the dashboard.')
                return
        if args.command == 'setup':
            update_config({'level': 2})
        if read_config()['level'] == 0:
            parser.error('Ghost Files is off. Run mdc ghosts enable --level 1 first.')
        if args.command == 'ofrenda':
            from .ghosts.ofrenda import markdown
            print(markdown(), end='')
            return
        if args.command == 'scan':
            from .ghosts.finder import find_ghosts
            from .ghosts.haunt import fallback
            warnings = []
            ghosts = find_ghosts(warnings=warnings)
            results = {g.path: fallback(g) for g in ghosts}
            if read_config()['level'] == 2 and not args.no_llm:
                from .ghosts.haunt import narrate
                from .ghosts.jobs import Job
                from .ghosts.ollama_manager import OllamaManager, setup_status
                manager = OllamaManager()
                config = read_config()
                try:
                    status = setup_status(config['model'])
                    if status['state'] == 'INSTALLED_NOT_RUNNING' and config['auto_start_ollama'] and config['setup'].get('start_consent') is True:
                        manager.start_server(Job())
                        status = setup_status(config['model'])
                    if status['state'] == 'READY':
                        narrate(ghosts[:25], config['model'], Job(), lambda g, out: results.update({g.path: out}))
                finally:
                    manager.stop()
            rows = [{**g.to_dict(), **results[g.path]} for g in ghosts]
            if args.json:
                print(json.dumps({'ghosts': rows, 'warnings': warnings}, indent=2))
            else:
                for row in rows:
                    print(f"[{row['final_verdict']}] {row['path']} ({row['size_bytes']} bytes)\n  {row['haunting']}\n  {row['reason']}")
                print(f'{len(rows)} ghosts. Review and banish individual items in the dashboard.')
                for warning in warnings:
                    print(warning, file=sys.stderr)
            return
        from .ghosts.jobs import Job
        from .ghosts.ollama_manager import OllamaManager, save_setup, setup_status
        manager, job = OllamaManager(), Job()
        job.progress = lambda step, message, pct=None: print(f'{step}: {message}' + (f' ({pct:.0f}%)' if pct is not None else ''), flush=True)
        try:
            if args.command == 'remove-ai':
                config = read_config()['setup']
                models = [m for m in config.get('models_pulled_by_mdc', []) if consent(f'Remove model {m}, downloaded by Mac Deep Cleaner?', args.yes)]
                uninstall = config.get('installed_by_mdc') in ('brew', 'app') and consent('Remove the Ollama installation created by Mac Deep Cleaner? Your ~/.ollama folder is retained.', args.yes)
                if models or uninstall:
                    manager.remove({'models': models, 'uninstall': bool(uninstall)}, job)
                else:
                    print('No AI components selected for removal.')
                return
            model = args.model or read_config()['model']
            status = setup_status(model)
            if not args.model and not read_config()['setup'].get('model_selected'):
                model = status['recommended_model']
                status = setup_status(model)
            if status.get('port_conflict'):
                raise RuntimeError('Port 11434 is occupied by an unrecognized server.')
            print(json.dumps(status, indent=2))
            required = { 'install': status['state'] == 'NOT_INSTALLED',
                         'start': status['state'] in ('NOT_INSTALLED', 'INSTALLED_NOT_RUNNING'),
                         'pull': model not in status['models'] }
            size = next(m['approx_gb'] for m in status['catalog'] if m['id'] == model)
            if required['pull'] and status['free_gb'] < size * 1.5 + 1:
                raise RuntimeError(f'This model needs {size * 1.5 + 1:.1f} GB free. Use level 1.')
            questions = {'install': 'Install Ollama using ' + status['install_method'] + '?',
                         'start': 'Allow Mac Deep Cleaner to start Ollama on loopback when needed?',
                         'pull': f'Download {model} (about {size} GB, needs {size * 1.5 + 1:.1f} GB free)?'}
            for step, needed in required.items():
                if needed and not consent(questions[step], args.yes):
                    update_config({'level': 1})
                    print('Setup declined. Ghost Files remains available without AI.')
                    return
            update_config({'model': model})
            save_setup(model_selected=True)
            if required['install']:
                manager.install(job, status['install_method'])
            if required['start']:
                save_setup(start_consent=True)
                manager.start_server(job)
            if required['pull']:
                manager.pull(model, job)
            from .ghosts.finder import Ghost
            from .ghosts.llm import haunt_one, unload_model
            try:
                print(haunt_one(Ghost('', 'Caches', 'org.example.lantern', 'Lantern', 1024, 31, 'high'), model)['haunting'])
            finally:
                unload_model(model)
            print('Ghosts + AI is ready. Narration stays on this Mac.')
        except (Exception, KeyboardInterrupt):
            if args.command != 'remove-ai':
                update_config({'level': 1})
            raise
        finally:
            manager.stop()
    except (APIError, OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Cancelled. Completed setup steps are retained.\n')
