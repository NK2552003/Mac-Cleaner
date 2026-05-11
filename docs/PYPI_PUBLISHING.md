# Publishing to PyPI (pypi.org) — mac-deep-cleaner (v1.2.0)

## What you’ll publish
This project is configured to build with `setuptools` from `pyproject.toml` (PEP 621). The package name is:

- **mac-deep-cleaner**

## Prerequisites
1. Create a PyPI account.
2. Create an API token (recommended over passwords):
   - PyPI → Account settings → API tokens
3. Install tooling:
```bash
python3 -m pip install --upgrade build twine
```

## Build distributions
From the repository root:

```bash
python3 -m build
```

This creates:
- `dist/*.tar.gz`
- `dist/*.whl`

## Upload to PyPI
```bash
twine upload dist/*
```

## If authentication fails (optional)
Use an API token stored as an environment variable (recommended):

```bash
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="YOUR_PYPI_API_TOKEN"
twine upload dist/*
```

## Verify the release
- Check the package page: https://pypi.org/project/mac-deep-cleaner/
- Install from the uploaded version:
```bash
pip install mac-deep-cleaner==1.2.0
```

## Upload automation (optional)
If you want to keep credentials out of shell history:
- Use your CI secret store to set `TWINE_USERNAME` and `TWINE_PASSWORD`.

## Quick checklist for v1.2.0
- `pyproject.toml` → `project.version = "1.2.0"`
- `README.md` / docs reflect v1.2.0
- `python3 -m build` produces valid wheel + sdist
- `twine upload dist/*` succeeds
