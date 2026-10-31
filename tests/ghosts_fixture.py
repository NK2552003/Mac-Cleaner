"""Browser fixture: fake Library and simulated Ollama; never touches user files or AI."""
import contextlib
import io
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_deep_cleaner import feature_config
from mac_deep_cleaner.common import fingerprint
from mac_deep_cleaner.ghosts import finder, haunt, llm, ofrenda, ollama_manager
from mac_deep_cleaner.scanner import Scanner
from mac_deep_cleaner.server import LocalServer
from mac_deep_cleaner.service import CleanerService

with tempfile.TemporaryDirectory(prefix='mdc-ghost-ui-') as directory, contextlib.ExitStack() as stack:
    root = Path(directory).resolve()
    for target, value in [('mac_deep_cleaner.feature_config.CONFIG',root/'config.json'),
        ('mac_deep_cleaner.ghosts.ofrenda.LEDGER',root/'ofrenda.json'),
        ('mac_deep_cleaner.ghosts.haunt.CACHE',root/'cache.json'),
        ('mac_deep_cleaner.cleanup.HOME',str(root)),('mac_deep_cleaner.cleanup.IS_MAC',False),
        ('mac_deep_cleaner.ghosts.finder.APP_DIRS',[])]:
        stack.enter_context(patch(target,value))
    roots = {k:root/'Library'/k for k in ('Caches','Preferences','Application Support')}
    for base in roots.values(): base.mkdir(parents=True)
    for kind,name,size in [('Caches','org.moonlit.lantern',1_400_000),
        ('Preferences','org.paper.atlas.plist',240_000),
        ('Application Support','Forgotten Notes',320_000)]:
        (roots[kind]/name).write_bytes(b'x'*size)
    stack.enter_context(patch.object(finder,'LEFTOVER_DIRS',roots))
    state = {'installed':False, 'running':False, 'models':{}}
    def status(model):
        return {'state':('READY' if model in state['models'] else 'RUNNING_NO_MODEL') if state['running'] else ('INSTALLED_NOT_RUNNING' if state['installed'] else 'NOT_INSTALLED'),
            'binary':'/fixture/ollama' if state['installed'] else None, 'version':'0.19.0' if state['running'] else None,
            'models':list(state['models']), 'catalog':ollama_manager.MODELS, 'install_method':'brew',
            'warning':'', 'error':'', 'ram_gb':16, 'free_gb':48, 'recommended_model':'llama3.2:3b'}
    def install(self, job, method):
        job.check();state['installed']=True
        binary=root/'ollama';binary.write_text('fixture')
        ollama_manager.save_setup(installed_by_mdc='brew',installed_path=str(binary),installed_identity=list(fingerprint(str(binary))))
    def start(self, job):
        job.check();state['running']=True
        ollama_manager.save_setup(started_by_mdc=True)
    def pull(self, model, job):
        job.check();state['models'][model]='fixture-digest'
        ollama_manager.save_setup(models_pulled_by_mdc=[model],model_digests={model:'fixture-digest'})
    def remove(self, body, job):
        for model in body['models']: state['models'].pop(model,None)
        if body['uninstall']:state['installed']=False;state['running']=False
        ollama_manager.save_setup(models_pulled_by_mdc=list(state['models']),installed_by_mdc=None if body['uninstall'] else 'brew')
        feature_config.update_config({'level':1})
    for name, function in [('install',install),('start_server',start),('pull',pull),('remove',remove)]:
        stack.enter_context(patch.object(ollama_manager.OllamaManager,name,function))
    stack.enter_context(patch.object(ollama_manager,'setup_status',status))
    stack.enter_context(patch.object(llm,'haunt_one',lambda g,m: {'haunting':f'{g.name_guess} lingers softly, keeping a corner of your Mac warm.', 'verdict':'likely_safe', 'reason':'Review the deterministic verdict before letting go.'}))
    stack.enter_context(patch.object(llm,'unload_model',lambda m:None))
    service=CleanerService(SimpleNamespace(view='settings'), {'mode':'normal','min_mb':0,'pinned':[]})
    service.scanner=Scanner(quiet=True)
    service.scanner.done=True
    service.scan_id='fixture-scan'
    server=LocalServer(service)
    artifacts=Path('/tmp/mdc-ghost-check');artifacts.mkdir(exist_ok=True)
    (artifacts/'launch-url').write_text(server.url)
    print('Ghost Files fixture ready',flush=True)
    try:server.serve_forever()
    finally:server.server_close();service.close()
