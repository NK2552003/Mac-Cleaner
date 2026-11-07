"""Audit or complete offline packs using Google Cloud Translation Basic.

Only shipped interface strings are sent. Google charges may apply. Credentials
are read from MDC_TRANSLATE_API_KEY or a hidden prompt, never saved. Each validated
batch is saved atomically, so interrupted generation can be resumed.
"""
import argparse
import getpass
import html
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.localization import NoRedirect, validate_pack

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


def encode(source):
    """Protect interpolation slots, names and quantities with nontranslation spans."""
    parts, protected, start = [], [], 0
    for match in TOKENS.finditer(source):
        parts.append(html.escape(source[start:match.start()]))
        parts.append(f'<span class="notranslate" translate="no" id="mdc-{len(protected)}">'
                     + html.escape(match[0]) + '</span>')
        protected.append(match[0])
        start = match.end()
    parts.append(html.escape(source[start:]))
    return ''.join(parts), protected


class TranslationText(HTMLParser):
    """Accept only the spans we sent and return plain text suitable for a pack."""
    def __init__(self, protected):
        super().__init__(convert_charrefs=True)
        self.protected, self.parts, self.seen = protected, [], []
        self.active, self.value = None, []

    def handle_starttag(self, tag, attrs):
        identifier = dict(attrs).get('id', '')
        if tag != 'span' or self.active is not None or not re.fullmatch(r'mdc-\d+', identifier):
            raise ValueError('Provider returned unexpected HTML')
        self.active = int(identifier[4:])
        self.value = []

    def handle_endtag(self, tag):
        if tag != 'span' or self.active is None:
            raise ValueError('Provider returned unbalanced HTML')
        index = self.active
        if index >= len(self.protected) or ''.join(self.value) != self.protected[index]:
            raise ValueError('Provider altered a protected token')
        self.parts.append(self.protected[index])
        self.seen.append(index)
        self.active = None

    def handle_data(self, value):
        (self.parts if self.active is None else self.value).append(value)

    def handle_comment(self, value):
        raise ValueError('Provider returned unexpected HTML')

    def handle_decl(self, value):
        raise ValueError('Provider returned unexpected HTML')


def decode(value, protected):
    parser = TranslationText(protected)
    parser.feed(value)
    parser.close()
    if parser.active is not None or sorted(parser.seen) != list(range(len(protected))):
        raise ValueError('Provider omitted or duplicated protected tokens')
    text = ''.join(parser.parts).strip()
    # NMT sometimes renders UI chevrons as escaped ASCII angle brackets. Keep
    # their navigation meaning while the shipped pack remains HTML-free.
    text = text.replace('<', '‹').replace('>', '›')
    if not text or any(c in text for c in '<>\x00\u202e\u202d'):
        raise ValueError(f'Provider returned invalid plain text: {text!r}')
    return text


def provider_error(error, key):
    """Report useful credential/quota diagnostics without leaking credentials."""
    try:
        payload = json.loads(error.read(64_000)).get('error', {})
        reasons = [d.get('reason', '') for d in payload.get('details', []) if isinstance(d, dict)]
        if 'API_KEY_SERVICE_BLOCKED' in reasons:
            detail = ('API_KEY_SERVICE_BLOCKED: allow Cloud Translation API '
                      '(translate.googleapis.com) in this key\'s API restrictions')
        elif 'SERVICE_DISABLED' in reasons:
            detail = 'SERVICE_DISABLED: enable Cloud Translation API in the Google Cloud project'
        else:
            detail = payload.get('message', 'Check credentials, billing and quota')
    except (ValueError, AttributeError, TypeError):
        detail = 'Check credentials, billing and quota'
    return f'Google Cloud HTTP {error.code}: {str(detail).replace(key, "[REDACTED]")}'


def request_batch(batch, locale, key, stop):
    encoded = [encode(source) for source in batch]
    body = urllib.parse.urlencode({'q': [value for value, _ in encoded], 'source': 'en',
                                  'target': locale, 'format': 'html'}, doseq=True).encode()
    request = urllib.request.Request(
        'https://translation.googleapis.com/language/translate/v2', data=body,
        headers={'X-Goog-Api-Key': key, 'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    for attempt in range(6):
        if stop.is_set():
            raise RuntimeError('Generation cancelled after another locale failed')
        try:
            with opener.open(request, timeout=45) as response:
                payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError('Translation response too large')
            values = json.loads(payload)['data']['translations']
            if not isinstance(values, list) or len(values) != len(batch):
                raise ValueError('Incomplete translation batch')
            translated = {source: decode(value['translatedText'], protected)
                          for source, value, (_, protected) in zip(batch, values, encoded)}
            validate_pack({'locale': locale, 'messages': translated})
            return translated
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise RuntimeError(provider_error(error, key)) from None
            detail = f'Google Cloud HTTP {error.code}'
            retry_after = error.headers.get('Retry-After', '')
        except (TimeoutError, urllib.error.URLError):
            detail, retry_after = 'Translation network request failed', ''
        if attempt == 5:
            raise RuntimeError(detail + '; retry limit reached') from None
        delay = max(min(60, 2 ** (attempt + 1)), int(retry_after) if retry_after.isdigit() else 0)
        print(f'{locale}: {detail}; retrying in {delay}s', flush=True)
        stop.wait(delay)


def usable_messages(document, catalog):
    generated = document.get('source') == 'google-machine-translation'
    return {source: value for source, value in document['messages'].items()
            if source in catalog and (source in INVARIANT or generated
                                      or (source != value and len(source) <= 90))}


def protected_tokens_intact(source, translated):
    return all(translated.count(token) >= count for token, count in Counter(TOKENS.findall(source)).items())


def save(path, messages):
    document = {'locale': path.stem, 'source': 'google-machine-translation',
                'messages': dict(sorted(messages.items()))}
    validate_pack(document)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def complete(path, catalog, key, retry_unchanged=False, stop=None, retranslate=()):
    stop = stop or threading.Event()
    data = json.loads(path.read_text(encoding='utf-8'))
    messages = usable_messages(data, catalog)
    missing = [source for source in catalog if source not in INVARIANT and
               (source not in messages or source in retranslate
                or (retry_unchanged and messages[source] == source)
                or not protected_tokens_intact(source, messages[source]))]
    batches, batch, size = [], [], 0
    for source in missing:
        length = len(encode(source)[0])
        if batch and (size + length > 5000 or len(batch) >= 64):
            batches.append(batch)
            batch, size = [], 0
        batch.append(source)
        size += length
    if batch:
        batches.append(batch)
    for source in INVARIANT & set(catalog):
        messages[source] = source
    print(f'{path.stem}: {len(missing)} entries to translate; {len(batches)} batches', flush=True)
    for index, batch in enumerate(batches):
        translated = request_batch(batch, path.stem, key, stop)
        candidate = {**messages, **translated}
        save(path, candidate)
        messages = candidate
        print(f'{path.stem}: {index + 1}/{len(batches)} batches saved', flush=True)
    save(path, messages)


def audit(paths, catalog):
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--check', action='store_true', help='Fail for missing entries or known English filler')
    parser.add_argument('--locales', nargs='+')
    parser.add_argument('--key-prompt', action='store_true', help='Read the API key with a hidden terminal prompt')
    parser.add_argument('--retry-unchanged', action='store_true', help='Ask Google to reconsider unchanged entries')
    parser.add_argument('--retranslate', action='append', default=[], metavar='SOURCE',
                        help='Regenerate this exact catalog message (repeatable)')
    parser.add_argument('--prune-stale', action='store_true', help='Remove retired catalog keys from packs without networking')
    parser.add_argument('--workers', type=int, default=1, choices=range(1, 5))
    parser.add_argument('--report', type=Path, help='Write missing and unchanged entries as JSON for review')
    args = parser.parse_args()
    paths = sorted((ROOT / 'locales').glob('*.json'))
    if args.locales:
        unknown = set(args.locales) - {p.stem for p in paths}
        if unknown:
            parser.error('Unknown bundled locales: ' + ', '.join(sorted(unknown)))
        paths = [p for p in paths if p.stem in args.locales]
    key = os.environ.get('MDC_TRANSLATE_API_KEY', '')
    if args.generate and args.key_prompt:
        key = getpass.getpass('Google Cloud API key: ')
    if args.generate and not key:
        parser.error('Set MDC_TRANSLATE_API_KEY or use --key-prompt')
    catalog = json.loads((ROOT / 'messages.json').read_text(encoding='utf-8'))
    if set(args.retranslate) - set(catalog):
        parser.error('--retranslate requires an exact message from the English catalog')
    if args.prune_stale:
        for path in paths:
            document = json.loads(path.read_text(encoding='utf-8'))
            document['messages'] = {k: v for k, v in document['messages'].items() if k in catalog}
            validate_pack(document)
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            temporary.replace(path)
    if args.generate:
        stop = threading.Event()
        failure = None
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(complete, path, catalog, key, args.retry_unchanged, stop, args.retranslate): path for path in paths}
            for job in as_completed(jobs):
                try:
                    job.result()
                except (APIError, CancelledError, RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
                    if failure is None:
                        failure = f'{jobs[job].stem}: {str(error).replace(key, "[REDACTED]")}'
                        stop.set()
                        for pending in jobs:
                            pending.cancel()
        if failure:
            raise SystemExit(failure + '; generation stopped. Completed batches are saved.')
    report = audit(paths, catalog)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    missing_total = sum(len(result['missing']) for result in report.values())
    print(f'Total: {len(paths)} locales; {missing_total} missing translations')
    if args.check and missing_total:
        raise SystemExit(f'{missing_total} missing translations across the bundled packs')
    if args.check and any(result['damaged_tokens'] or result['stale'] for result in report.values()):
        raise SystemExit('Packs contain damaged protected tokens or retired catalog entries; see the audit report')


if __name__ == '__main__':
    main()
