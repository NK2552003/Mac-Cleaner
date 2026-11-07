"""Build bundled offline packs from public interface strings only.

Developer-only, explicit network operation. Google's public translation endpoint
returns one result per q parameter. Requests are throttled, HTTP 429 is backed
off, and validated batches are journaled. This is never run by the application.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_deep_cleaner.localization import validate_pack
from scripts.complete_locales import INVARIANT, ROOT

PROTECTED = sorted(INVARIANT | {'Google Cloud Translation', 'Google Cloud', 'Mac Cleaner',
    'LaunchAgent', 'LaunchDaemon', 'Spotlight', 'Time Machine', 'App Store', 'iCloud',
    'Safari', 'Chrome', 'Firefox', 'Edge', 'Xcode', 'Docker', 'Git', 'GitHub',
    'Python', 'Node.js', 'npm', 'pnpm', 'yarn', 'pip', 'Gradle', 'Android', 'Java', 'Rust', 'Cargo',
    'Steam', 'Adobe', 'DaVinci', 'Final Cut', 'Lightroom', 'Capture One', 'APFS',
    'NTFS', 'ExFAT', 'FAT32', 'HFS+', 'Base', 'MDC_TRANSLATE_API_KEY'}, key=len, reverse=True)
PATTERN = re.compile(r'\{\w+\}|' + '|'.join(r'(?<!\w)' + re.escape(word) + r'(?!\w)' for word in PROTECTED)
                     + r'|(?<!\w)\d+(?:[,.]\d+)*(?:%| GB| MB| KB)?(?!\w)')
last_request = 0.0


def encode(source):
    values = []
    def protect(match):
        values.append(match[0])
        return '__MDC_' + str(9000 + len(values) - 1) + '__'
    return PATTERN.sub(protect, source), values


def decode(value, protected):
    seen = []
    def restore(match):
        index = int(match[1]) - 9000
        if 0 <= index < len(protected):
            seen.append(index)
            return protected[index]
        return match[0]
    result = re.sub(r'__[^_]*?_\s*(\d+)\s*__', restore, value, flags=re.IGNORECASE)
    if sorted(seen) != list(range(len(protected))):
        raise ValueError(f'Provider altered a protected placeholder: {value!r}; expected {protected!r}')
    return result.translate(str.maketrans({'<': '‹', '>': '›', '\u202e': None, '\u202d': None}))


def request(strings, locale, interval):
    global last_request
    encoded = [encode(source) for source in strings]
    query = urllib.parse.urlencode({'client': 'gtx', 'sl': 'en', 'tl': locale,
                                    'q': [value[0] for value in encoded]}, doseq=True)
    url = 'https://translate.googleapis.com/translate_a/t?' + query
    for attempt in range(8):
        time.sleep(max(0, last_request + interval - time.monotonic()))
        last_request = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.loads(response.read(2_000_001))
            if not isinstance(data, list) or len(data) != len(strings) or not all(isinstance(v, str) for v in data):
                raise ValueError('Provider returned an incomplete batch')
            results = []
            for source, value, (_, protected) in zip(strings, data, encoded):
                try:
                    results.append(decode(value, protected))
                except ValueError as error:
                    if len(strings) == 1:
                        raise
                    print(f'{locale}: retry one message: {source!r}: {error}', flush=True)
                    results.append(None)
            return results
        except urllib.error.HTTPError as error:
            if error.code == 429 or error.code >= 500:
                delay = max(int(error.headers.get('Retry-After', 0) or 0), min(300, 30 * 2**attempt))
                print(f'{locale}: HTTP {error.code}; backing off {delay}s', flush=True)
                time.sleep(delay)
                continue
            raise
        except (TimeoutError, urllib.error.URLError) as error:
            print(f'{locale}: network retry: {type(error).__name__}', flush=True)
            time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError('Provider unavailable after bounded retries; rerun to resume')


def save(path, data):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--locales', nargs='*')
    parser.add_argument('--interval', type=float, default=2.5)
    parser.add_argument('--journal', type=Path, default=Path('/tmp/mdc-translations-journal'))
    args = parser.parse_args()
    if not args.generate:
        parser.error('--generate is required to send shipped interface strings for translation')
    args.journal.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / 'messages.json').read_text())
    for path in sorted((ROOT / 'locales').glob('*.json')):
        if args.locales and path.stem not in args.locales:
            continue
        data = json.loads(path.read_text())
        journal_path = args.journal / path.name
        journal = json.loads(journal_path.read_text()) if journal_path.exists() else {}
        messages = {k: v for k, v in data['messages'].items() if k in catalog
                    and ((k != v and len(k) <= 90) or k in INVARIANT)}
        messages.update({k: v for k, v in journal.items() if k in catalog})
        for source in INVARIANT & set(catalog):
            messages[source] = source
        missing = [source for source in catalog if source not in messages]
        batches, current, size = [], [], 0
        for source in missing:
            encoded, _ = encode(source)
            if current and (size + len(encoded) > 3700 or len(current) >= 128):
                batches.append(current)
                current, size = [], 0
            current.append(source)
            size += len(encoded)
        if current:
            batches.append(current)
        print(f'{path.stem}: {len(missing)} missing; {len(batches)} batches', flush=True)
        for number, batch in enumerate(batches):
            try:
                values = request(batch, path.stem, args.interval)
            except ValueError:
                # Retry individual messages only for alignment/placeholder errors,
                # never split or increase traffic in response to rate limiting.
                values = []
                for source in batch:
                    values.extend(request([source], path.stem, args.interval))
            updates = {source: value for source, value in zip(batch, values) if value is not None}
            journal.update(updates)
            save(journal_path, journal)
            for source, value in zip(batch, values):
                if value is None:
                    updates[source] = request([source], path.stem, args.interval)[0]
            candidate = {'locale': path.stem, 'source': 'google-machine-translation',
                         'messages': dict(sorted({**messages, **updates}.items()))}
            validate_pack(candidate)
            journal.update(updates)
            save(journal_path, journal)
            save(path, candidate)
            messages = candidate['messages']
            print(f'{path.stem}: saved {number + 1}/{len(batches)}; {len(messages)}/{len(catalog)} messages', flush=True)
        document = {'locale': path.stem, 'source': 'google-machine-translation', 'messages': dict(sorted(messages.items()))}
        validate_pack(document)
        save(path, document)
        print(f'{path.stem}: COMPLETE', flush=True)


if __name__ == '__main__':
    main()
