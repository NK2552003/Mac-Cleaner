"""Compatibility entry point for offline AI-authored language-pack merging.

Use --merge PACK.json, then --check. No translation network calls are supported.
"""
from complete_locales import main

if __name__ == '__main__':
    main()
