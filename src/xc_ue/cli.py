from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError, version

WORKSPACE_ENTRY = "00_工程总控/工程执行层/统一运行入口.py"


def _version() -> str:
    try:
        return version("xc-ue")
    except PackageNotFoundError:
        from . import __version__

        return __version__


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(
            "xc-ue is a workspace stub only. Run the engine from the repo root:\n"
            f"  python {WORKSPACE_ENTRY} --help",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(
        prog="xcue",
        description="XC-UE workspace stub (not the L1/L2/L3 engine).",
    )
    parser.add_argument("--health", action="store_true", help="Print a minimal JSON health payload.")
    parser.add_argument("--version", action="store_true", help="Print the installed package version.")
    args = parser.parse_args(argv)

    if args.version:
        print(_version())
        return 0
    if args.health:
        print(
            json.dumps(
                {
                    "ok": True,
                    "package": "xc_ue",
                    "version": _version(),
                    "engine_entry": WORKSPACE_ENTRY,
                    "note": "workspace-only stub",
                },
                ensure_ascii=False,
            )
        )
        return 0
    parser.print_help()
    return 2
