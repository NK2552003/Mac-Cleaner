"""Bounded narration, private cache, deterministic fallback for every failure."""
import hashlib
import json
from pathlib import Path

from ..feature_config import atomic_json
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


def fallback(ghost):
    # Size and age already appear on the card; the line says what the leftover is.
    verdict = rule_verdict(ghost)
    line = LINES.get(ghost.kind, '{n} left residual files behind.').format(n=ghost.name_guess)
    return {'haunting': line, 'verdict': None, 'final_verdict': verdict,
            'reason': REASONS[verdict], 'source': 'rules'}


def _ungrounded(text, allowed):
    import re
    if re.search(r'https?:|/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+|~[/\\]', text):
        return True
    return any(n not in allowed for n in re.findall(r'\d+', text))


def ground(ghost, output):
    """Repair model text that invents numbers or paths; the deterministic line replaces it."""
    import re
    from .llm import human
    allowed = set(re.findall(r'\d+', f'{human(ghost.size_bytes)} {ghost.age_days} {ghost.name_guess} {ghost.bundle_id}'))
    text = ' '.join(re.split(r'(?<=[.!?])\s+', output['haunting'].strip())[:2])
    if _ungrounded(text, allowed) or len(text) < 6:
        text = fallback(ghost)['haunting']
    reason = output['reason']
    if _ungrounded(reason, allowed):
        reason = REASONS[rule_verdict(ghost)]
    return {**output, 'haunting': text[:350], 'reason': reason[:180]}


def cache_key(ghost, model):
    data = (ghost.path, ghost.identity, ghost.size_bytes, ghost.age_days, ghost.confidence, model, 5)
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def narrate(ghosts, model, job, receive):
    from .llm import haunt_one, unload_model, valid_output
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
            key = cache_key(ghost, model)
            result = fallback(ghost)
            if connected:
                try:
                    output = ground(ghost, valid_output(cache[key]) if key in cache else haunt_one(ghost, model))
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
