"""校验 L2 业务评测语料（v1 / v2）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from l2_corpus_validate_lib import validate_dataset

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
V2 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2"


def main() -> int:
    parser = argparse.ArgumentParser(description="L2 业务评测语料校验")
    parser.add_argument("--dataset-v1", action="store_true", help="校验 v1 pilot")
    parser.add_argument("--dataset-v2", action="store_true", help="校验 v2 pilot")
    parser.add_argument("--dataset-root", type=str, default="", help="自定义语料根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if args.dataset_root:
        root = Path(args.dataset_root)
    elif args.dataset_v2:
        root = V2
    elif args.dataset_v1:
        root = V1
    else:
        root = V2

    if not root.is_dir():
        print(f"MISSING_DATASET: {root}")
        return 1

    report = validate_dataset(root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report["validation_ok"]:
            print("VALIDATION_OK")
        else:
            print("VALIDATION_FAIL")
            for case in report["cases"]:
                if case["errors"]:
                    print(f"\n{case['case_id']}:")
                    for err in case["errors"]:
                        print(f"  - {err}")
    return 0 if report["validation_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
