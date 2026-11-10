"""Audit offline packs or merge AI-authored translations. No network or API keys."""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_deep_cleaner.localization import validate_pack
ROOT = Path(__file__).resolve().parents[1] / 'mac_deep_cleaner/web'

INVARIANT = {'Mac Deep Cleaner', 'Homebrew', 'macOS', 'Ollama', 'Finder', 'UUID', 'APFS', 'JSON', 'CPU', 'GB', 'MB', 'KB', 'TB', 'B', 'RAM', 'SSD', 'HDD', 'GitHub', 'DuckDuckGo', 'Google', 'Pillow', 'ffmpeg', 'ffprobe', 'HTTPStorages', 'LaunchAgents', 'LaunchDaemons'}
PROTECTED = INVARIANT | {
    'Google Cloud Translation', 'Google Cloud', 'Mac Cleaner', 'LaunchAgent',
    'LaunchDaemon', 'Spotlight', 'Time Machine', 'App Store', 'iCloud', 'Safari',
    'Chrome', 'Firefox', 'Edge', 'Xcode', 'Docker', 'Git', 'Python', 'Node.js',
    'npm', 'pnpm', 'yarn', 'pip', 'Gradle', 'Android', 'Java', 'Rust', 'Cargo',
    'Steam', 'Adobe', 'DaVinci', 'Final Cut', 'Lightroom', 'Capture One', 'NTFS',
    'ExFAT', 'FAT32', 'HFS+', 'MDC_TRANSLATE_API_KEY', 'I UNDERSTAND',
}
TOKENS = re.compile(
    r'\{\w+\}|'
    + '|'.join(r'(?<!\w)' + re.escape(word) + r'(?!\w)'
               for word in sorted(PROTECTED, key=lambda value: (-len(value), value)))
    + r'|(?<!\w)\d+(?:[,.]\d+)*(?:%| GB| MB| KB)?(?!\w)'
)


def protected_tokens_intact(source, translated):
    """Check that placeholders, product names, and numbers survive translation."""
    return all(translated.count(token) >= count for token, count in Counter(TOKENS.findall(source)).items())


def usable_messages(document, catalog):
    """Keep current translations, allowing reviewed invariant source strings."""
    return {source: value for source, value in document['messages'].items()
            if source in catalog and (source in INVARIANT or source != value
                                      or document.get('source') in ('google-machine-translation', 'bundled-ai-reviewed'))}


def merge(path, additions, catalog):
    """Validate an offline pack and atomically replace its UTF-8 target catalog."""
    document = json.loads(path.read_text(encoding='utf-8'))
    if additions['locale'] != path.stem:
        raise ValueError('Locale mismatch')
    validate_pack(additions)
    for source, translated in additions['messages'].items():
        if not protected_tokens_intact(source, translated):
            raise ValueError('Translation changed protected tokens')
    document['messages'] = {k: v for k, v in {**document['messages'], **additions['messages']}.items() if k in catalog}
    document['source'] = 'bundled-ai-reviewed'
    validate_pack(document)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def audit(paths, catalog):
    """Report missing, stale, untranslated, or token-damaged entries in offline packs."""
    report = {}
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        # Catalog extraction can retire source messages before packs are rebuilt.
        stale = sorted(set(data['messages']) - set(catalog))
        validate_pack({**data, 'messages': {k: v for k, v in data['messages'].items() if k in catalog}})
        messages = usable_messages(data, catalog)
        missing = sorted(set(catalog) - messages.keys())
        unchanged = sorted(s for s in catalog if messages.get(s) == s and s not in INVARIANT)
        damaged = sorted(s for s, value in messages.items() if not protected_tokens_intact(s, value))
        report[path.stem] = {'total': len(catalog), 'missing': missing, 'unchanged': unchanged,
                             'stale': stale, 'damaged_tokens': damaged}
        print(f'{path.stem}: {len(catalog) - len(missing)}/{len(catalog)} messages; '
              f'{len(unchanged)} unchanged source strings to review; {len(damaged)} token errors')
    return report


def main():
    """Merge an optional offline pack, audit selected locales, and enforce check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--locales', nargs='+')
    parser.add_argument('--merge', type=Path, help='Merge an AI-authored JSON language pack')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'messages.json').read_text(encoding='utf-8'))
    if args.merge:
        additions = validate_pack(json.loads(args.merge.read_text(encoding='utf-8')))
        merge(ROOT / 'locales' / (additions['locale'] + '.json'), additions, catalog)
    paths = sorted((ROOT / 'locales').glob('*.json'))
    if args.locales:
        paths = [p for p in paths if p.stem in args.locales]
    report = audit(paths, catalog)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.check and any(r['missing'] or r['damaged_tokens'] or r['stale'] for r in report.values()):
        raise SystemExit('Language packs need attention; see the audit report')


if __name__ == '__main__':
    main()
