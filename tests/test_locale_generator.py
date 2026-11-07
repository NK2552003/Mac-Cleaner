"""Offline merging rejects invalid AI translations before changing bundled files."""
import json
import pytest
from mac_deep_cleaner import localization
from scripts import complete_locales as generator


def test_merge_validates_placeholders_and_protected_tokens(tmp_path, monkeypatch):
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
    monkeypatch.setattr(localization, 'catalog', lambda:['Settings'])
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale':'fr','messages':{}}))
    with pytest.raises(ValueError, match='Locale'):
        generator.merge(path, {'locale':'de','messages':{'Settings':'Einstellungen'}}, ['Settings'])


def test_audit_reports_missing_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(localization, 'catalog', lambda:['Settings','Restore'])
    path = tmp_path / 'fr.json'
    path.write_text(json.dumps({'locale':'fr','messages':{'Settings':'Paramètres'}}))
    assert generator.audit([path], ['Settings','Restore'])['fr']['missing'] == ['Restore']
