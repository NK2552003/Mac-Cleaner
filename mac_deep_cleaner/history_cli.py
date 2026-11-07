"""Command-line access to the shared Trash journal."""
import argparse
import json
from .errors import APIError
from .history import History


def main(command, argv):
    parser = argparse.ArgumentParser(prog=f'mdc {command}')
    if command == 'restore':
        parser.add_argument('id', help='Cleanup history')
    args = parser.parse_args(argv)
    try:
        result = History().restore(args.id) if command == 'restore' else History().records()
        print(json.dumps(result, indent=2))
    except (APIError, OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')
