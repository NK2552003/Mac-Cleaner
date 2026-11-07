"""Keep branch versions monotonic and reject stale release candidates."""
import argparse
import ast
from pathlib import Path
import subprocess

from packaging.version import Version


def read_version(source):
    """Read the literal runtime version without executing another branch's code."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == '__version__'
            for target in node.targets
        ):
            return Version(ast.literal_eval(node.value))
    raise ValueError('Runtime version constant is missing')


def check_base(candidate, base):
    if Version(candidate) < Version(base):
        raise ValueError(f'Version downgrade: {candidate} is older than base branch {base}')


def is_new_release(candidate, latest, releases):
    version = Version(candidate)
    return version > Version(latest) and all(version != Version(v) for v in releases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = 'mac_deep_cleaner/__init__.py'
    candidate = read_version((root / path).read_text())
    base = read_version(subprocess.check_output(
        ['git', 'show', f'{args.base_ref}:{path}'], cwd=root, text=True))
    check_base(str(candidate), str(base))
    print(f'Version {candidate} is compatible with base branch {base}.')


if __name__ == '__main__':
    main()
