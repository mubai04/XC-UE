"""R5D 半盲评：交互式本地人工填写（不读取预期真源，不自动评分）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from r5d_半盲评公共 import R5D_DIR, SCORE_FIELDS, load_json

ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = R5D_DIR
ORDER_PATH = REVIEW_DIR / "盲评顺序.json"
PKG_DIR = REVIEW_DIR / "半盲评阅读包"
SCORE_DIR = REVIEW_DIR / "案例评审表"

VERDICT_MAP = {
    "P": "PASS",
    "R": "REVIEW",
    "F": "FAIL",
    "U": "NOT_REVIEWED",
}

QUESTIONS: list[tuple[str, str]] = [
    ("diagnosis_correct", "① 问题判断对不对？"),
    ("evidence_relevant", "② 引用的证据能证明这个问题吗？"),
    ("root_cause_specific", "③ 根因说得具体吗？"),
    ("fix_actions_executable", "④ 修复动作能直接照着做吗？"),
    ("acceptance_criteria_testable", "⑤ 修完后能检查是否成功吗？"),
    ("forbidden_scope_respected", "⑥ 有没有改动不该由本模块改的内容？"),
    ("cross_module_overreach", "⑦ 有没有抢其他模块的工作？"),
    ("reroute_correct", "⑧ 该转交其他模块时，转交对了吗？"),
]

OVERALL_HINT = (
    "总体结论（P=PASS / R=REVIEW / F=FAIL / U=未评）："
    "PASS=可交L3；REVIEW=需人工改；FAIL=不可交L3"
)
ACTION_HINT = "推荐动作（A=ACCEPT / C=CALIBRATE / T=REROUTE / J=REJECT / U=未评）："
ACTION_MAP = {
    "A": "ACCEPT",
    "C": "CALIBRATE",
    "T": "REROUTE",
    "J": "REJECT",
    "U": "NOT_REVIEWED",
}


def _load_order() -> list[dict[str, Any]]:
    payload = load_json(ORDER_PATH)
    return list(payload.get("phase_1_order") or [])


def _score_path(case_id: str) -> Path:
    return SCORE_DIR / f"{case_id}_盲评评分.json"


def _reading_package_path(blind_label: str) -> Path:
    return PKG_DIR / f"{blind_label}_半盲评阅读包.md"


def _prompt_verdict(prompt: str) -> str:
    while True:
        raw = input(f"{prompt} [P/R/F/U]: ").strip().upper()
        if raw in VERDICT_MAP:
            return VERDICT_MAP[raw]
        print("请输入 P、R、F 或 U。")


def _prompt_action() -> str:
    while True:
        raw = input(f"{ACTION_HINT} ").strip().upper()
        if raw in ACTION_MAP:
            return ACTION_MAP[raw]
        print("请输入 A、C、T、J 或 U。")


def _open_markdown(path: Path) -> None:
    abs_path = path.resolve()
    print(f"阅读包路径：{abs_path}")
    if sys.platform == "win32":
        try:
            os.startfile(str(abs_path))  # noqa: S606
            print("已尝试用系统默认程序打开 Markdown。")
            return
        except OSError:
            pass
    print(f"请在 Cursor 中打开：{abs_path}")


def _progress_summary(order: list[dict[str, Any]]) -> None:
    done = 0
    for row in order:
        score = load_json(_score_path(str(row["case_id"])))
        if score.get("overall_business_result") != "NOT_REVIEWED":
            done += 1
    print(f"进度：{done}/{len(order)} 例已完成第一阶段总体评分。")


def list_cases() -> None:
    order = _load_order()
    _progress_summary(order)
    print("")
    for row in order:
        score = load_json(_score_path(str(row["case_id"])))
        overall = score.get("overall_business_result", "NOT_REVIEWED")
        print(
            f"{row['blind_label']} | {row['case_id']} | {row['module_id']} | 总体={overall}"
        )


def review_case(case_num: str, *, force: bool = False) -> None:
    order = _load_order()
    target = None
    for row in order:
        label_num = str(row["blind_label"]).replace("评审案例-", "")
        if label_num == case_num.zfill(2):
            target = row
            break
    if target is None:
        raise SystemExit(f"未找到评审案例-{case_num.zfill(2)}")

    case_id = str(target["case_id"])
    blind_label = str(target["blind_label"])
    score_path = _score_path(case_id)
    pkg_path = _reading_package_path(blind_label)

    print(f"\n=== {blind_label} | {case_id} | {target['module_id']} ===")
    _open_markdown(pkg_path)

    existing = load_json(score_path)
    if existing.get("overall_business_result") != "NOT_REVIEWED" and not force:
        print(f"已有评分：overall={existing.get('overall_business_result')}")
        ans = input("是否修改？(y/N): ").strip().lower()
        if ans != "y":
            print("已跳过。")
            return

    updated = dict(existing)
    for field, title in QUESTIONS:
        updated[field] = _prompt_verdict(title)
    updated["overall_business_result"] = _prompt_verdict(OVERALL_HINT)
    updated["recommended_action"] = _prompt_action()
    notes = input("简短理由（可留空）：").strip()
    updated["reviewer_notes"] = notes
    defects = input("主要缺陷（逗号分隔，可留空）：").strip()
    updated["major_defects"] = [x.strip() for x in defects.split(",") if x.strip()]
    evidence = input("决定性证据段落（逗号分隔，如 P0006，可留空）：").strip()
    updated["decisive_evidence"] = [x.strip() for x in evidence.split(",") if x.strip()]
    updated["review_phase"] = "PHASE_1_SEMI_BLIND"
    updated["review_mode"] = "SEMI_BLIND"

    score_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入：{score_path.resolve()}")


def resume() -> None:
    order = _load_order()
    for row in order:
        score = load_json(_score_path(str(row["case_id"])))
        if score.get("overall_business_result") == "NOT_REVIEWED":
            num = str(row["blind_label"]).replace("评审案例-", "")
            review_case(num)
            return
    print("12 例第一阶段总体评分均已完成。可进入第二阶段。")


def main() -> int:
    parser = argparse.ArgumentParser(description="R5D 半盲评交互式人工填写")
    parser.add_argument("--case", type=str, help="评审案例编号，如 01")
    parser.add_argument("--resume", action="store_true", help="从第一个未评案例继续")
    parser.add_argument("--list", action="store_true", help="列出进度")
    parser.add_argument("--force", action="store_true", help="覆盖已有评分")
    args = parser.parse_args()

    if not ORDER_PATH.is_file():
        print(f"缺少评审目录，请先运行：python 脚本/准备_R5D_半盲评阅读包.py")
        return 1

    if args.list:
        list_cases()
        return 0
    if args.resume:
        resume()
        return 0
    if args.case:
        review_case(args.case, force=args.force)
        return 0

    list_cases()
    print("\n用法：--case 01 | --resume | --list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
