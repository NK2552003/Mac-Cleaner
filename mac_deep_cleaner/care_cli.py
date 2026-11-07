"""Command-line access to the v3.5 local care tools."""

import argparse
import json
from pathlib import Path

from . import scheduler
from .errors import APIError
from .history import History


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mdc care", description="Local cleanup history, rules, and scheduling"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("history", help="List recorded Trash moves")
    restore = commands.add_parser(
        "restore", help="Restore one unchanged history entry without overwriting files"
    )
    restore.add_argument("id")
    schedule = commands.add_parser(
        "schedule", help="Install or remove the weekly user launch agent"
    )
    schedule.add_argument("action", choices=["status", "enable", "disable"])
    schedule.add_argument("--weekday", type=int, default=0, help="0 Sunday through 6 Saturday")
    schedule.add_argument("--hour", type=int, default=10)
    schedule.add_argument(
        "--yes", action="store_true", help="Consent to installing the weekly cleanup agent"
    )
    scheduled = commands.add_parser("scheduled-run", help="Run the conservative scheduled policy")
    scheduled.add_argument("--preview", action="store_true")
    rules = commands.add_parser("rules", help="Validate and optionally install a JSON rules file")
    rules.add_argument("file")
    rules.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "history":
            result = History().records()
        elif args.command == "restore":
            result = History().restore(args.id)
        elif args.command == "scheduled-run":
            result = scheduler.run_scheduled(args.preview)
        elif args.command == "schedule":
            if args.action == "status":
                result = scheduler.status()
            elif args.action == "enable":
                if not args.yes:
                    parser.error(
                        "Review the policy with mdc care scheduled-run --preview, then use --yes to enable weekly Trash moves."
                    )
                result = scheduler.configure(True, args.weekday, args.hour)
            else:
                result = scheduler.configure(False)
        else:
            from .feature_config import atomic_json
            from .profiles import rules_file, validate_rules

            result = validate_rules(json.loads(Path(args.file).read_text()))
            if args.install:
                atomic_json(rules_file(), result)
        print(json.dumps(result, indent=2))
    except (APIError, OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
