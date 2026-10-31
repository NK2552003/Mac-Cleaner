"""App research and explanation combining web search, GitHub repos, and open-weight LLMs."""
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from ..feature_config import MODEL_IDS, read_config
from .llm import clean, human
from .local_http import local_json

RESEARCH_CACHE = {}


def inspect_leftover_dir(path, limit=25):
    """Safely inspects files and directories inside the leftover folder."""
    files = []
    p = Path(path)
    if not p.is_dir():
        return files
    try:
        entries = list(p.iterdir())
    except OSError:
        return files

    for entry in entries[:limit]:
        if entry.is_symlink():
            continue
        try:
            st = entry.stat()
            size = st.st_size if entry.is_file() else sum(
                f.stat().st_size for f in entry.rglob('*') if f.is_file() and not f.is_symlink()
            ) if entry.is_dir() else 0
            files.append({
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'size_bytes': size,
                'size_fmt': human(size),
            })
        except OSError:
            pass

    files.sort(key=lambda x: -x['size_bytes'])
    return files


def search_web_and_github(query):
    """Fetches real-world web and GitHub context without paid API keys."""
    sources = []
    clean_q = re.sub(r'[^a-zA-Z0-9\s-]', ' ', query).strip()

    # 1. GitHub Repository Search
    try:
        url = f'https://api.github.com/search/repositories?q={urllib.parse.quote(clean_q)}&per_page=2'
        req = urllib.request.Request(url, headers={'User-Agent': 'MacDeepCleaner/2.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for item in data.get('items', [])[:2]:
                desc = item.get('description')
                if desc:
                    sources.append({
                        'title': f"GitHub: {item.get('full_name')}",
                        'snippet': desc.strip(),
                        'url': item.get('html_url')
                    })
    except Exception:
        pass

    # 2. DuckDuckGo HTML Search
    try:
        url = f'https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_q)}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            snippets = re.findall(r'<a[^>]+class=[\"\']result__snippet[\"\'][^>]*>(.*?)</a>', html, re.DOTALL)
            for s in snippets[:3]:
                clean_s = re.sub(r'<[^>]+>', '', s).strip()
                if clean_s and len(clean_s) > 20:
                    sources.append({
                        'title': 'Web Search',
                        'snippet': clean_s,
                        'url': f'https://duckduckgo.com/?q={urllib.parse.quote(clean_q)}'
                    })
    except Exception:
        pass

    return sources


def synthesize_with_model(ghost, files, sources, model):
    """Uses a local open-weight model in Ollama to summarize the app's purpose and usage."""
    if model not in MODEL_IDS:
        return None

    files_text = ', '.join(f"{f['name']} ({f['size_fmt']})" for f in files[:8]) or 'None'
    sources_text = '\n'.join(f"- {s['title']}: {s['snippet']}" for s in sources[:4]) or 'No web results available.'

    prompt = f"""You are an expert macOS software analyst.
Analyze these leftovers from an uninstalled app or tool:
- App Name: {ghost.name_guess}
- Location: {ghost.path} ({human(ghost.size_bytes)})
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
            'options': {'temperature': 0.2, 'num_predict': 250},
            'messages': [
                {'role': 'system', 'content': 'You explain Mac app leftovers accurately and safely based on provided search context. Reply with JSON only matching the schema.'},
                {'role': 'user', 'content': prompt}
            ]
        }, timeout=25)
        content = json.loads(reply['message']['content'])
        return {
            'summary': clean(content.get('summary', ''), 300),
            'usage': clean(content.get('usage', ''), 300),
            'data_stored': clean(content.get('data_stored', ''), 200),
            'recommendation': clean(content.get('recommendation', ''), 200),
            'model': model
        }
    except Exception:
        return None


def explain_ghost(ghost, model=None, force_refresh=False):
    """Builds a comprehensive explanation with web/GitHub search and local file inspection."""
    cache_key = f"{ghost.path}:{model}:{ghost.size_bytes}"
    if not force_refresh and cache_key in RESEARCH_CACHE:
        return RESEARCH_CACHE[cache_key]

    files = inspect_leftover_dir(ghost.path)
    sources = search_web_and_github(ghost.name_guess)

    ai_result = None
    if model:
        ai_result = synthesize_with_model(ghost, files, sources, model)

    if ai_result:
        summary = ai_result['summary']
        usage = ai_result['usage']
        data_stored = ai_result['data_stored']
        recommendation = ai_result['recommendation']
        model_name = ai_result['model']
    else:
        # High quality synthesis from search snippets and file inspection
        top_snippet = next((s['snippet'] for s in sources if len(s['snippet']) > 30), '')
        if top_snippet:
            summary = top_snippet
            usage = f"Commonly used by macOS users or developers for {ghost.name_guess} tasks and workflows."
        else:
            summary = f"{ghost.name_guess} is a macOS application or developer tool that stores data in {ghost.kind}."
            usage = f"Installed when running or testing {ghost.name_guess} on this Mac."

        data_stored = f"Stores {len(files)} items ({human(ghost.size_bytes)}) including configuration, session data, and caches."
        recommendation = (
            "Likely safe to delete if you no longer use this application. Moving to Trash allows recovery if needed."
            if ghost.confidence == 'high' or ghost.kind in ('Caches', 'Saved State', 'Logs')
            else "Review the files before deleting. Settings or local configurations may be needed if you reinstall the app."
        )
        model_name = 'web-search'

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
    }

    RESEARCH_CACHE[cache_key] = result
    return result
