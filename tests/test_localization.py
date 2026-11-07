"""Language selection, placeholder safety, and locale-scoped local AI regressions."""
import json
from types import SimpleNamespace

import pytest

from mac_deep_cleaner import localization
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.ghosts import haunt, llm, research
from mac_deep_cleaner.ghosts.finder import Ghost
from mac_deep_cleaner.ghosts.rules import REASONS

LOCALES = sorted(path.stem for path in (localization.WEB / 'locales').glob('*.json'))


@pytest.mark.parametrize('locale', LOCALES)
def test_bundled_locale_is_complete_and_preserves_protected_text(locale):
    from scripts.complete_locales import protected_tokens_intact
    document = json.loads((localization.WEB / 'locales' / f'{locale}.json').read_text())
    messages = document['messages']
    assert set(messages) == set(localization.catalog())
    localization.validate_pack(document)
    for source, translated in messages.items():
        assert protected_tokens_intact(source, translated), (locale, source)
    for source in ['Settings', 'Permanent deletion cannot be undone.',
                   'Type I UNDERSTAND to include them']:
        assert messages[source] != source, (locale, source)
    # Dutch uses the same imperative "Open"; Japanese must not retain English.
    if locale == 'ja':
        assert messages['Open Mac Deep Cleaner'] == 'Mac Deep Cleaner を開く'
    if locale == 'id':
        assert messages['Open Mac Deep Cleaner'] == 'Buka Mac Deep Cleaner'


@pytest.mark.parametrize('locale', LOCALES)
def test_selected_locale_reaches_model_and_cache(locale, monkeypatch):
    requests = []
    def reply(route, body, **kwargs):
        requests.append(body)
        return {'message': {'content': json.dumps({
            'haunting': 'A local description.', 'reason': 'Review these files.', 'verdict': 'review'})}}
    monkeypatch.setattr(llm, 'local_json', reply)
    ghost = Ghost('/private/owner/cache', 'Caches', 'org.example.app', 'Example', 2048, 50, 'high')
    llm.haunt_one(ghost, 'llama3.2:3b', locale=locale)
    system = requests[0]['messages'][0]['content']
    assert f'({locale})' in system
    assert 'Keep JSON field names and verdict enum values unchanged' in system
    assert ghost.path not in json.dumps(requests)
    assert haunt.cache_key(ghost, 'llama3.2:3b', locale) != haunt.cache_key(ghost, 'llama3.2:3b', 'en')


def test_pack_placeholders_must_be_preserved(monkeypatch):
    monkeypatch.setattr(localization, 'catalog', lambda: ['Showing {count} files for {name}.'])
    for invalid in ['Fichiers.', 'Fichiers {total} pour {name}.', 'Fichiers {count} {count} pour {name}.']:
        with pytest.raises(APIError, match='placeholders'):
            localization.validate_pack({'locale': 'fr', 'messages': {'Showing {count} files for {name}.': invalid}})
    localization.validate_pack({'locale': 'fr', 'messages': {
        'Showing {count} files for {name}.': 'Pour {name} : {count} fichiers.'}})


def test_private_values_are_inserted_after_translation(monkeypatch):
    seen = []
    def load(locale):
        seen.append(locale)
        return {'messages': {'{n} left diagnostic log files.': '{n} a laissé des journaux.'}}
    monkeypatch.setattr(localization, 'load_pack', load)
    ghost = Ghost('/private/path', 'Logs', 'org.example', 'Private {name}', 1, 1, 'high')
    result = haunt.fallback(ghost, 'fr')
    assert result['haunting'] == 'Private {name} a laissé des journaux.'
    assert seen == ['fr', 'fr']


def test_inspector_never_searches_web_and_keeps_verdict(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('Unexpected web request'))
    monkeypatch.setattr(research, 'RESEARCH_CACHE', {})
    ghost = Ghost(str(tmp_path), 'Caches', 'org.example.app', 'Example', 2048, 50, 'high')
    assert research.explain_ghost(ghost, verdict='keep')['recommendation'] == REASONS['keep']
    calls = []
    def model(g, files, sources, model, locale):
        calls.append(locale)
        return {'summary': f'{locale} summary', 'usage': f'{locale} usage',
                'data_stored': f'{locale} data', 'recommendation': 'Delete immediately.', 'model': model}
    monkeypatch.setattr(research, 'synthesize_with_model', model)
    for locale in ('fr', 'ja', 'fr'):
        result = research.explain_ghost(ghost, model='llama3.2:3b', locale=locale, verdict='keep')
        assert result['summary'] == f'{locale} summary'
        assert result['recommendation'] != 'Delete immediately.'
    assert calls == ['fr', 'ja']


def test_inspector_ignores_symlinks_and_bounds_listing(tmp_path):
    for i in range(30):
        (tmp_path / f'{i}.txt').write_text('fixture')
    link = tmp_path / 'link'
    link.symlink_to(tmp_path)
    assert research.inspect_leftover_dir(link) == []
    files = research.inspect_leftover_dir(tmp_path, limit=5)
    assert len(files) <= 5
    assert 'link' not in {file['name'] for file in files}


def test_inspector_model_uses_language_and_rejects_incomplete_json(monkeypatch):
    requests = []
    def reply(route, body, **kwargs):
        requests.append(body)
        return {'message': {'content': '{}'}}
    monkeypatch.setattr(research, 'local_json', reply)
    ghost = Ghost('/private/owner/cache', 'Caches', 'org.example.app', 'Example', 2048, 50, 'high')
    assert research.synthesize_with_model(ghost, [], [], 'llama3.2:3b', locale='ar') is None
    assert '(ar)' in requests[0]['messages'][0]['content']
    assert ghost.path not in json.dumps(requests)


def test_runtime_report_messages_match_catalog_templates(monkeypatch):
    monkeypatch.setattr(localization, 'load_pack', lambda locale: {'messages': {
        'Download untouched for {days} days.': 'Téléchargement inutilisé depuis {days} jours.'}})
    assert localization.translate('Download untouched for 40 days.', 'fr') == 'Téléchargement inutilisé depuis 40 jours.'


def test_english_filler_is_not_counted_as_translated(tmp_path, monkeypatch):
    monkeypatch.setattr(localization, 'WEB', tmp_path)
    monkeypatch.setattr(localization, 'pack_directory', lambda: tmp_path / 'custom')
    (tmp_path / 'locales').mkdir()
    (tmp_path / 'messages.json').write_text(json.dumps(['Settings', 'Restore']))
    (tmp_path / 'locales/fr.json').write_text(json.dumps({'locale': 'fr', 'messages': {
        'Settings': 'Paramètres', 'Restore': 'Restore'}}))
    result = localization.load_pack('fr')
    assert result['translated'] == 1
    assert result['total'] == 2


def test_wrong_script_ai_uses_localized_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(haunt, 'CACHE', tmp_path / 'ai.json')
    monkeypatch.setattr(llm, 'haunt_one', lambda *a, **k: {
        'haunting': 'This application left temporary files.',
        'reason': 'These files can be rebuilt.', 'verdict': 'likely_safe'})
    monkeypatch.setattr(llm, 'unload_model', lambda *a: None)
    ghost = Ghost('/private/cache', 'Caches', 'org.example.app', 'Example', 2048, 50, 'high')
    outputs = []
    job = SimpleNamespace(check=lambda: None, progress=lambda *a: None)
    haunt.narrate([ghost], 'llama3.2:3b', job, lambda g, output: outputs.append(output), locale='ar')
    assert outputs[0]['source'] == 'rules'
    assert outputs[0]['haunting'] == haunt.fallback(ghost, 'ar')['haunting']
    assert llm.output_script_matches(outputs[0]['haunting'], 'ar', ('Example',))
    assert not json.loads(haunt.CACHE.read_text())


def test_app_name_cannot_mask_wrong_script_output():
    assert not llm.output_script_matches('日本語 left temporary files.', 'ja', ('日本語',))
    assert llm.output_script_matches('Example の一時ファイルが残っています。', 'ja', ('Example',))
