"""Compatibility entry point for the offline locale audit and merge tool.

Use --merge with an AI-authored JSON pack, then --check to validate coverage.
"""
from complete_locales import main

if __name__ == '__main__':
    main()
