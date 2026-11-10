"""Offline merging rejects invalid AI translations before changing bundled files."""
import json
from pathlib import Path
import pytest
from mac_deep_cleaner import localization
from scripts import complete_locales as generator


def test_merge_validates_placeholders_and_protected_tokens(tmp_path, monkeypatch):
    """Reject damaged translations before replacing the original language pack."""
    source = 'Show {count} files in Finder.'
    monkeypatch.setattr(localization, 'catalog', lambda:[source])
    path = tmp_path / 'fr.json'
    original = json.dumps({'locale':'fr','messages':{}})
    path.write_text(original)
    for invalid in ['Afficher les fichiers dans Finder.', 'Afficher {count} fichiers.']:
        with pytest.raises((ValueError, localization.APIError)):
            generator.merge(path, {'locale':'fr','messages':{source:invalid}}, [source])
        assert path.read_text() == original
    translation = 'Afficher {count} fichiers dans Finder.'
    generator.merge(path, {'locale':'fr','messages':{source:translation}}, [source])
    assert json.loads(path.read_text())['messages'][source] == translation


def test_merge_rejects_wrong_locale(tmp_path, monkeypatch):
    """Reject a pack whose locale does not match its destination filename."""
    monkeypatch.setattr(localization, 'catalog', lambda:['Settings'])
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale':'fr','messages':{}}))
    with pytest.raises(ValueError, match='Locale'):
        generator.merge(path, {'locale':'de','messages':{'Settings':'Einstellungen'}}, ['Settings'])


def test_audit_reports_missing_without_network(tmp_path, monkeypatch):
    """Report untranslated catalog entries using only local pack data."""
    monkeypatch.setattr(localization, 'catalog', lambda:['Settings','Restore'])
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale':'fr','messages':{'Settings':'Paramètres'}}))
    assert generator.audit([path], ['Settings','Restore'])['fr']['missing'] == ['Restore']


def test_partial_merge_preserves_utf8_with_non_utf8_default(tmp_path, monkeypatch):
    """Merging and auditing must ignore the platform's default text encoding."""
    catalog = ['Settings', 'Restore']
    monkeypatch.setattr(localization, 'catalog', lambda: catalog)
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale': 'fr', 'messages': {'Settings': 'Paramètres'}},
                               ensure_ascii=False), encoding='utf-8')
    original_open = Path.open
    def latin1_default(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        return original_open(self, mode, buffering, None if 'b' in mode else encoding or 'latin-1', errors, newline)
    monkeypatch.setattr(Path, 'open', latin1_default)
    generator.merge(path, {'locale': 'fr', 'messages': {'Restore': 'Rétablir'}}, catalog)
    messages = json.loads(path.read_bytes().decode('utf-8'))['messages']
    assert messages == {'Settings': 'Paramètres', 'Restore': 'Rétablir'}
    assert not generator.audit([path], catalog)['fr']['missing']
