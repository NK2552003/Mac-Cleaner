"""An on-device remembrance ledger. Record only successful Trash moves."""
import datetime
import json
from pathlib import Path

from ..feature_config import atomic_json

LEDGER = Path.home() / '.local/share/mac-deep-cleaner/ofrenda.json'


def records():
    try:
        value = json.loads(LEDGER.read_text(encoding='utf-8'))
        return [v for v in value if isinstance(v, dict) and all(k in v for k in ('name', 'size_bytes', 'date'))] if isinstance(value, list) else []
    except (OSError, ValueError):
        return []


def remember(ghosts):
    entries = records()
    for ghost in ghosts:
        entries.append({'name': ghost.name_guess, 'size_bytes': ghost.size_bytes,
            'date': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'farewell': 'Moved to Trash'})
    atomic_json(LEDGER, entries)


def markdown():
    def escape(value):
        return str(value).replace('\n', ' ').replace('\r', ' ').replace('\\', '\\\\').replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')
    lines = ['# Cleanup History', '', 'Leftover files moved to the Trash by Mac Deep Cleaner.', '',
             'Files still occupy disk space until you empty the Trash yourself in Finder.', '',
             '| Application / Item | Bytes | Date (UTC) |', '| --- | ---: | --- |']
    for entry in records():
        lines.append(f"| {escape(entry['name'])} | {int(entry['size_bytes'])} | {escape(entry['date'])} |")
    return '\n'.join(lines) + '\n'
