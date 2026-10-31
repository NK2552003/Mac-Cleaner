"""The switch lives in core so disabled launches never import this package."""
from ..feature_config import atomic_json, read_config, update_config

__all__ = ['atomic_json', 'read_config', 'update_config']
