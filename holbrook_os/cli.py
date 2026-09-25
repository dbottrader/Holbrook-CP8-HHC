import argparse
import json
import sys

from .runtime import HolbrookRuntime


def main() -> None:
    parser = argparse.ArgumentParser(prog="holbrook")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("prompt")

    verify = sub.add_parser("verify")
    verify.add_argument("receipt", help="JSON receipt file, or - for stdin")

    args = parser.parse_args()

    if args.command == "run":
        print(json.dumps(HolbrookRuntime().run(args.prompt).to_dict(), indent=2))
        return

    if args.receipt == "-":
        raw = sys.stdin.read()
    else:
        with open(args.receipt, encoding="utf-8") as fh:
            raw = fh.read()
    print("valid" if HolbrookRuntime.verify(json.loads(raw)) else "invalid")


if __name__ == "__main__":
    main()
