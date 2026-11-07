"""Local-only, language-aware explanations of leftover files."""
import json
import urllib.parse
from pathlib import Path

from ..feature_config import MODEL_IDS
from ..localization import language_instruction, translate
from .llm import clean, human, output_script_matches
from .local_http import local_json
from .rules import REASONS, final_verdict

RESEARCH_CACHE = {}


def inspect_leftover_dir(path, limit=25):
    """Safely inspects files and directories inside the leftover folder."""
    files = []
    p = Path(path)
    if p.is_symlink() or not p.is_dir():
        return files
    try:
        from itertools import islice
        entries = list(islice(p.iterdir(), limit))
    except OSError:
        return files

    for entry in entries[:limit]:
        if entry.is_symlink():
            continue
        try:
            st = entry.stat()
            # Do not recursively walk arbitrary leftover trees on the HTTP thread.
            size = st.st_size if entry.is_file() else 0
            files.append({
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'size_bytes': size,
                'size_fmt': human(size) if entry.is_file() else '—',
            })
        except OSError:
            pass

    files.sort(key=lambda x: -x['size_bytes'])
    return files


def synthesize_with_model(ghost, files, sources, model, locale="en"):
    """Uses a local open-weight model in Ollama to summarize the app's purpose and usage."""
    if model not in MODEL_IDS:
        return None

    files_text = ', '.join(f"{f['name']} ({f['size_fmt']})" for f in files[:8]) or 'None'
    sources_text = '\n'.join(f"- {s['title']}: {s['snippet']}" for s in sources[:4]) or 'No web results available.'

    prompt = f"""You are an expert macOS software analyst.
Analyze these leftovers from an uninstalled app or tool:
- App Name: {ghost.name_guess}
- Size: {human(ghost.size_bytes)}
- Leftover Type: {ghost.kind}
- Files inside: {files_text}
- Web / GitHub search findings:
{sources_text}

Provide a clear, accurate explanation for the user in JSON with these exact keys:
- summary: 1-2 sentences on what this application or developer tool is and who created it.
- usage: 1-2 sentences explaining what developers/users use it for and common workflows.
- data_stored: 1 sentence explaining what the files in this leftover directory contain.
- recommendation: 1 sentence advising whether it is safe to delete and what happens if removed.
"""

    schema = {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'usage': {'type': 'string'},
            'data_stored': {'type': 'string'},
            'recommendation': {'type': 'string'}
        },
        'required': ['summary', 'usage', 'data_stored', 'recommendation']
    }

    try:
        reply = local_json('/api/chat', {
            'model': model,
            'stream': False,
            'format': schema,
            'keep_alive': '5m',
            'options': {'temperature': 0.2, 'num_predict': 768},
            'messages': [
                {'role': 'system', 'content': 'Explain only the supplied facts. Do not invent an app creator or purpose. Reply with JSON only matching the schema.' + language_instruction(locale)},
                {'role': 'user', 'content': prompt}
            ]
        }, timeout=25)
        content = json.loads(reply['message']['content'])
        if not isinstance(content, dict) or any(not isinstance(content.get(key), str) or not content[key].strip() for key in schema['required']):
            return None
        if not all(output_script_matches(content[key], locale, (ghost.name_guess, ghost.bundle_id)) for key in schema['required']):
            return None
        return {
            'summary': clean(content.get('summary', ''), 300),
            'usage': clean(content.get('usage', ''), 300),
            'data_stored': clean(content.get('data_stored', ''), 200),
            'recommendation': clean(content.get('recommendation', ''), 200),
            'model': model
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def explain_ghost(ghost, model=None, force_refresh=False, locale="en", verdict=None):
    """Inspect locally; external search links are opened only by the user."""
    cache_key = (ghost.path, ghost.identity, model, ghost.size_bytes, locale, verdict)
    if not force_refresh and cache_key in RESEARCH_CACHE:
        return RESEARCH_CACHE[cache_key]

    files = inspect_leftover_dir(ghost.path)
    # Opening an inspector never sends app names or local metadata to the web.
    sources = []

    ai_result = None
    if model:
        ai_result = synthesize_with_model(ghost, files, sources, model, locale)

    if ai_result:
        summary = ai_result['summary']
        usage = ai_result['usage']
        data_stored = ai_result['data_stored']
        recommendation = ai_result['recommendation']
        model_name = ai_result['model']
    else:
        summary = translate('{name} has leftover files in {kind}.', locale,
                            name=ghost.name_guess, kind=translate(ghost.kind, locale))
        usage = translate('The application is not present in the scanned app folders. Its purpose cannot be verified from leftover files alone.', locale)
        data_stored = translate('Showing up to {count} entries. Total leftover size: {size}.', locale,
                                count=len(files), size=human(ghost.size_bytes))
        model_name = None

    # Model prose must never replace the deterministic safety assessment.
    recommendation = translate(REASONS[final_verdict(ghost, verdict)], locale)

    q = urllib.parse.quote(ghost.name_guess)
    result = {
        'name': ghost.name_guess,
        'bundle_id': ghost.bundle_id,
        'kind': ghost.kind,
        'size_bytes': ghost.size_bytes,
        'size_fmt': human(ghost.size_bytes),
        'age_days': ghost.age_days,
        'path': ghost.path,
        'confidence': ghost.confidence,
        'summary': summary,
        'usage': usage,
        'data_stored': data_stored,
        'recommendation': recommendation,
        'files': files,
        'sources': sources,
        'search_links': {
            'google': f"https://www.google.com/search?q={q}",
            'github': f"https://github.com/search?q={q}",
            'duckduckgo': f"https://duckduckgo.com/?q={q}"
        },
        'model': model_name,
        'locale': locale,
    }

    if len(RESEARCH_CACHE) >= 128:
        RESEARCH_CACHE.pop(next(iter(RESEARCH_CACHE)))
    RESEARCH_CACHE[cache_key] = result
    return result
