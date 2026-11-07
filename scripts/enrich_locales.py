"""Compatibility entry point for the locale audit/generator.

Do not pad missing translations with English: that masks incomplete coverage.
Use --generate with MDC_TRANSLATE_API_KEY to fill actual translations.
"""
from complete_locales import main

if __name__ == '__main__':
    main()
