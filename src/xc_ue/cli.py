from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version


def _version() -> str:
    try:
        return version("xc-ue")
    except PackageNotFoundError:
        from . import __version__

        return __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xcue",
        description="XC-UE minimal package entry point.",
    )
    parser.add_argument("--health", action="store_true", help="Print a minimal JSON health payload.")
    parser.add_argument("--version", action="store_true", help="Print the installed package version.")
    args = parser.parse_args(argv)

    if args.version:
        print(_version())
        return 0
    if args.health:
        print(json.dumps({"ok": True, "package": "xc_ue", "version": _version()}, ensure_ascii=False))
        return 0
    parser.print_help()
    return 0

