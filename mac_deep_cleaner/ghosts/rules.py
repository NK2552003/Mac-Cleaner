"""The model may veto, never grant permission to remove files."""
RANK = {'keep': 0, 'review': 1, 'likely_safe': 2}
SAFE_KINDS = {'Caches', 'Logs', 'Saved State', 'HTTPStorages'}
REASONS = {'keep': 'The owning app could not be verified. Keep this unless you recognize it.',
           'review': 'Stored settings or app data may still matter. Review the contents first.',
           'likely_safe': 'No matching app was found in the scanned app folders; this is regenerable data.'}


def rule_verdict(ghost):
    if ghost.confidence != 'high' or ghost.bundle_id.startswith('com.apple.'):
        return 'keep'
    return 'likely_safe' if ghost.kind in SAFE_KINDS else 'review'


def final_verdict(ghost, model_verdict=None):
    rule = rule_verdict(ghost)
    if not isinstance(model_verdict, str) or model_verdict not in RANK:
        return rule
    return min((rule, model_verdict), key=RANK.__getitem__)
