"""Bounded narration, private cache, deterministic fallback for every failure."""
import hashlib
import json
from pathlib import Path

from ..feature_config import atomic_json
from ..localization import translate
from .rules import REASONS, final_verdict, rule_verdict

CACHE = Path.home() / '.cache/mac-deep-cleaner/ghosts.json'


LINES = {
    'Application Support': '{n} left configuration and saved settings behind in Application Support.',
    'Caches': '{n} left temporary cache files that can be safely rebuilt.',
    'Preferences': '{n} left preference files after the application was removed.',
    'Containers': '{n} left a sandboxed application container.',
    'Group Containers': '{n} left shared app-group data that related applications may still use.',
    'Saved State': '{n} left saved window state that is safely recreated when needed.',
    'Logs': '{n} left diagnostic log files.',
    'HTTPStorages': '{n} left cached network cookies and session data.'}


def fallback(ghost, locale="en"):
    # Size and age already appear on the card; the line says what the leftover is.
    verdict = rule_verdict(ghost)
    line = translate(LINES.get(ghost.kind, '{n} left residual files behind.'), locale, n=ghost.name_guess)
    return {'haunting': line, 'verdict': None, 'final_verdict': verdict,
            'reason': translate(REASONS[verdict], locale), 'source': 'rules'}


def _ungrounded(text, allowed):
    import re
    if re.search(r'https?:|/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+|~[/\\]', text):
        return True
    return any(n not in allowed for n in re.findall(r'\d+', text))


def ground(ghost, output, locale="en"):
    """Repair model text that invents numbers or paths; the deterministic line replaces it."""
    import re
    from .llm import human
    allowed = set(re.findall(r'\d+', f'{human(ghost.size_bytes)} {ghost.age_days} {ghost.name_guess} {ghost.bundle_id}'))
    text = ' '.join(re.split(r'(?<=[.!?])\s+', output['haunting'].strip())[:2])
    if _ungrounded(text, allowed) or len(text) < 6:
        text = fallback(ghost, locale)['haunting']
    reason = output['reason']
    if _ungrounded(reason, allowed):
        reason = translate(REASONS[rule_verdict(ghost)], locale)
    return {**output, 'haunting': text[:350], 'reason': reason[:180]}


def cache_key(ghost, model, locale="en"):
    data = (ghost.path, ghost.identity, ghost.size_bytes, ghost.age_days, ghost.confidence, model, locale, 7)
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def narrate(ghosts, model, job, receive, locale="en"):
    from .llm import haunt_one, output_script_matches, unload_model, valid_output
    try:
        cache = json.loads(CACHE.read_text(encoding='utf-8'))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError):
        cache = {}
    connected = True
    try:
        for index, ghost in enumerate(ghosts):
            job.check()
            key = cache_key(ghost, model, locale)
            result = fallback(ghost, locale)
            if connected:
                try:
                    raw = valid_output(cache[key]) if key in cache else (haunt_one(ghost, model) if locale == 'en' else haunt_one(ghost, model, locale=locale))
                    if not all(output_script_matches(raw[key], locale, (ghost.name_guess, ghost.bundle_id)) for key in ('haunting', 'reason')):
                        raise ValueError('The local model did not use the selected language.')
                    output = ground(ghost, raw, locale)
                    cache[key] = output
                    result = {**output, 'final_verdict': final_verdict(ghost, output['verdict']), 'source': 'ai'}
                except (OSError, ValueError, KeyError, TypeError):
                    result['ai_error'] = 'Local narration was unavailable. The deterministic description is shown.'
                    # Avoid one long timeout per remaining file when the server disappears.
                    connected = False
            job.check()
            receive(ghost, result)
            job.progress('haunt', f'Narrated {index + 1} of {len(ghosts)}', (index + 1) * 100 / max(1, len(ghosts)))
    finally:
        try:
            atomic_json(CACHE, dict(list(cache.items())[-1000:]))
        except OSError:
            pass  # Cache is an optimization, never a condition for completion.
        unload_model(model)
