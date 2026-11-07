"""Offline checks for resumable Google Cloud pack generation."""
import io
import json
import threading
import urllib.error
from urllib.parse import parse_qs

import pytest

from mac_deep_cleaner import localization
from scripts import complete_locales as generator


def test_protected_tokens_survive_reordering_and_entities():
    source = 'Show {count} files in Finder & keep 30 days.'
    encoded, protected = generator.encode(source)
    assert generator.decode(encoded, protected) == source
    translated = ('<span id="mdc-1">Finder</span> : '
                  '<span id="mdc-0">{count}</span> fichiers &amp; '
                  '<span id="mdc-2">30</span> jours.')
    assert generator.decode(translated, protected) == 'Finder : {count} fichiers & 30 jours.'
    assert generator.decode('Berikutnya &gt;', []) == 'Berikutnya ›'
    _, confirmation = generator.encode('Type I UNDERSTAND to include them')
    assert confirmation == ['I UNDERSTAND']
    assert not generator.protected_tokens_intact('Capture One cache.', 'Capturer un cache.')
    assert not generator.protected_tokens_intact('Type I UNDERSTAND to include them', 'Tapez JE COMPRENDS')
    assert generator.protected_tokens_intact('Type I UNDERSTAND to include them', 'Tapez I UNDERSTAND pour les inclure')
    for invalid in [encoded.replace('{count}', '{nombre}'),
                    encoded.replace('id="mdc-2"', 'id="mdc-1"'),
                    encoded + '<span id="mdc-0">{count}</span>',
                    '<b>Unexpected markup</b>', encoded + '\u202e']:
        with pytest.raises(ValueError):
            generator.decode(invalid, protected)


def test_audit_excludes_legacy_english_filler(tmp_path, monkeypatch):
    catalog = ['Settings', 'Restore', 'Homebrew']
    monkeypatch.setattr(localization, 'catalog', lambda: catalog)
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale': 'fr', 'messages': {
        'Settings': 'Paramètres', 'Restore': 'Restore', 'Homebrew': 'Homebrew'}}))
    report = generator.audit([path], catalog)['fr']
    assert report['missing'] == ['Restore']
    assert report['unchanged'] == []


def test_generation_resumes_only_after_validated_saved_batches(tmp_path, monkeypatch):
    catalog = [f'Static interface message {i}' for i in range(130)]
    monkeypatch.setattr(localization, 'catalog', lambda: catalog)
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale': 'fr', 'messages': {}}))
    calls = []

    def interrupted(batch, locale, key, stop):
        calls.append(batch)
        if len(calls) == 2:
            raise RuntimeError('Simulated provider outage')
        return {source: 'Traduit : ' + source for source in batch}

    monkeypatch.setattr(generator, 'request_batch', interrupted)
    with pytest.raises(RuntimeError, match='outage'):
        generator.complete(path, catalog, 'fixture-secret')
    saved = json.loads(path.read_text())['messages']
    assert saved and set(saved) == set(calls[0])
    assert 'fixture-secret' not in path.read_text()
    resumed = []

    def success(batch, locale, key, stop):
        resumed.extend(batch)
        return {source: 'Traduit : ' + source for source in batch}

    monkeypatch.setattr(generator, 'request_batch', success)
    generator.complete(path, catalog, 'fixture-secret')
    assert not set(saved).intersection(resumed)
    assert set(json.loads(path.read_text())['messages']) == set(catalog)


def test_invalid_batch_never_replaces_pack(tmp_path, monkeypatch):
    source = 'Showing {count} files.'
    monkeypatch.setattr(localization, 'catalog', lambda: [source])
    path = tmp_path / 'fr.json'
    original = json.dumps({'locale': 'fr', 'messages': {}})
    path.write_text(original)
    monkeypatch.setattr(generator, 'request_batch', lambda *args: {source: 'Fichiers.'})
    with pytest.raises(localization.APIError, match='placeholders'):
        generator.complete(path, [source], 'fixture-secret')
    assert path.read_text() == original


def test_cloud_errors_explain_restrictions_and_redact_key():
    def error(payload):
        return urllib.error.HTTPError('https://translation.googleapis.com', 403, 'Forbidden', {},
                                      io.BytesIO(json.dumps({'error': payload}).encode()))
    blocked = error({'details': [{'reason': 'API_KEY_SERVICE_BLOCKED'}]})
    assert 'allow Cloud Translation API' in generator.provider_error(blocked, 'fixture-secret')
    assert 'fixture-secret' not in generator.provider_error(error({'message': 'Invalid fixture-secret'}), 'fixture-secret')


def test_cloud_request_retries_quota_and_preserves_tokens(monkeypatch):
    source = 'Showing {count} files.'
    monkeypatch.setattr(localization, 'catalog', lambda: [source])
    requests, delays = [], []

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            if len(requests) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, 'Quota', {'Retry-After': '7'}, io.BytesIO())
            translated = 'Affichage de <span id="mdc-0">{count}</span> fichiers.'
            return io.BytesIO(json.dumps({'data': {'translations': [{'translatedText': translated}]}}).encode())

    monkeypatch.setattr(generator.urllib.request, 'build_opener', lambda *args: Opener())
    stop = threading.Event()
    monkeypatch.setattr(stop, 'wait', lambda delay: delays.append(delay))
    result = generator.request_batch([source], 'fr', 'fixture-secret', stop)
    assert result[source] == 'Affichage de {count} fichiers.'
    assert delays == [7]
    assert len(requests) == 2
    assert b'fixture-secret' not in requests[0].data
    assert 'fixture-secret' not in requests[0].full_url
    assert parse_qs(requests[0].data.decode())['format'] == ['html']
