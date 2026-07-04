"""
cathedral_os_tools.cli — Unified CLI Entry Point

Wraps lmc-init and evidence-ladder into a single command-line interface.

Usage:
    python -m cathedral_os_tools --help
    python -m cathedral_os_tools lmc-init --help
    python -m cathedral_os_tools evidence-ladder --help
"""

import argparse
import sys
from typing import Optional, List

from cathedral_os_tools.lmc_init import main as lmc_main
from cathedral_os_tools.evidence_ladder import main as ladder_main


def main(argv: Optional[List[str]] = None) -> int:
    """Unified CLI for cathedral_os_tools."""
    parser = argparse.ArgumentParser(
        prog="cathedral_os_tools",
        description="Cathedral-OS Tools — LMC Bootstrap + Evidence Ladder Enforcer",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    subparsers = parser.add_subparsers(dest="tool")

    # lmc-init subcommand
    lmc_parser = subparsers.add_parser(
        "lmc-init", aliases=["init"], help="Bootstrap an LMC-compliant project"
    )
    lmc_parser.add_argument("project_name", nargs="?", default=None)
    lmc_parser.add_argument("--path")
    lmc_parser.add_argument("--force", action="store_true")

    # evidence-ladder subcommand
    el_parser = subparsers.add_parser(
        "evidence-ladder",
        aliases=["ladder", "el"],
        help="Evidence Ladder Enforcer",
    )
    el_parser.add_argument("subcommand", nargs="?", default=None)
    el_parser.add_argument("--object-id", default="anonymous")
    el_parser.add_argument("--current")
    el_parser.add_argument("--requested")
    el_parser.add_argument("--receipts")
    el_parser.add_argument("--contradictions")
    el_parser.add_argument("--domain", default="general")
    el_parser.add_argument("--claim")

    args, remaining = parser.parse_known_args(argv)

    if args.tool in ("lmc-init", "init"):
        return lmc_main(remaining + ([args.project_name] if args.project_name else []))
    elif args.tool in ("evidence-ladder", "ladder", "el"):
        return ladder_main(remaining)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
