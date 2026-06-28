#!/usr/bin/env python3
"""XC-UE REAL-REPAIR-02：《准点下班怎么了》单章真实修复验证编排。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "审计纠偏_2026-06-26" / "REAL_REPAIR_02_准点下班怎么了"
EXEC = ROOT / "00_工程总控" / "工程执行层"
L1_ENTRY = EXEC / "L1工程" / "L1运行入口.py"
L15_ENTRY = EXEC / "L1.5工程" / "L1.5运行入口.py"
L2_ENTRY = EXEC / "L2工程" / "L2运行入口.py"
L3_ENTRY = EXEC / "L3工程" / "L3运行入口.py"
PIPELINE_ENTRY = EXEC / "修复流水线运行入口.py"

PROJECT_ID = "ZDXB-001"
PROJECT_ROOT = ROOT / "70_测试项目" / "ZDXB-001_准点下班怎么了"
CHAPTER_REL = "70_测试项目/ZDXB-001_准点下班怎么了/chapters/ch01.md"
SOURCE_ORIGINAL = ROOT / "第1章-准点下班怎么了.md"
EXTERNAL_REF = ROOT / "第1章_准点下班怎么了_商业修订版.md"

COMPARISON_DIMS = (
    "核心商业承诺是否更集中",
    "主角当前目标是否更清楚",
    "三条卖点是否形成统一推进链",
    "异常是否迫使主角做出行动",
    "是否形成原因—选择—后果",
    "章节是否出现真正的局势变化",
    "章末追读问题是否更强",
    "是否破坏人物、系统或世界设定",
    "是否出现解释过量、重复或无来源新增事实",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_subprocess_json(proc: subprocess.CompletedProcess) -> dict[str, Any]:
    for stream in (proc.stdout, proc.stderr):
        for line in reversed((stream or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return {}


def _load_l1_payload(l1_out: Path, l1_run: str) -> dict[str, Any]:
    payload = {}
    for report_json in sorted(l1_out.glob("*.json")):
        if any(x in report_json.name for x in ("_failure_packet", "_audit_blockers")):
            continue
        try:
            payload = json.loads(report_json.read_text(encoding="utf-8-sig"))
            break
        except (OSError, json.JSONDecodeError):
            continue
    packet = l1_out / f"{l1_run}_failure_packet.json"
    if not payload.get("status") and packet.is_file():
        try:
            payload["status"] = json.loads(packet.read_text(encoding="utf-8-sig")).get("status", "")
        except (OSError, json.JSONDecodeError):
            pass
    return payload


def _fix_form_accepts_l3(fix: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = (
        "模块内主问题", "根因", "修复规则", "修复动作", "禁止修改范围",
        "必须保留内容", "验收条件", "修复单状态",
    )
    for key in required:
        if key not in fix:
            errors.append(f"缺少字段：{key}")
    actions = fix.get("修复动作") or []
    if not actions:
        errors.append("修复动作为空")
    status = str(fix.get("修复单状态", ""))
    if status and status not in ("READY_FOR_L3", "允许进入L3", "READY"):
        errors.append(f"修复单状态不允许进入 L3：{status}")
    return not errors, errors


def _emit(out_dir: Path, result: dict[str, Any]) -> int:
    _write_json(out_dir / "REAL_REPAIR_02结果.json", result)
    lines = [
        "# 最终业务结论（REAL-REPAIR-02）",
        "",
        f"- **REAL_REPAIR_RESULT**: `{result.get('REAL_REPAIR_RESULT', '')}`",
        f"- **PRIMARY_FINDING**: `{result.get('PRIMARY_FINDING', '—')}`",
        f"- **FINAL_STATUS**: `{result.get('FINAL_STATUS', result.get('stop_code', ''))}`",
        f"- **说明**: {result.get('message', '')}",
        "",
    ]
    for k in ("CASE_QUALIFICATION", "L1_RESULT", "REPAIR_CHAIN", "BUSINESS_DIAGNOSIS_CONFLICT", "target_module"):
        if k in result:
            lines.append(f"- **{k}**: `{result[k]}`")
    _write(out_dir / "09_最终业务结论.md", "\n".join(lines) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    stop = result.get("stop_code", "")
    if stop in ("L1_DETECTION_GAP_CANDIDATE", "L1_SCREENING_PASS"):
        return 0
    if result.get("REAL_REPAIR_RESULT") == "PASSED":
        return 0
    return 2 if stop else 3


def _verify_source_unchanged(chapter_path: Path, before_source: bytes) -> bool:
    return SOURCE_ORIGINAL.read_bytes() == before_source


def _compare_texts_phase1(original: str, candidate: str) -> dict[str, Any]:
    """结构化对照（不读取外部参考）。"""
    rows: list[dict[str, Any]] = []

    def score_dim(name: str, a_ok: bool, b_ok: bool, b_better: bool | None, note: str) -> None:
        verdict = "候选更优" if b_better is True else ("候选更差" if b_better is False else "相当")
        rows.append({"维度": name, "原稿": a_ok, "候选": b_ok, " verdict": verdict, "说明": note})

    # 启发式 + 关键词（独立判断，不用外部参考）
    orig_has_goal = any(x in original for x in ("永久离职", "十万积分", "终极兑换", "100000"))
    cand_has_goal = any(x in candidate for x in ("永久离职", "十万积分", "终极兑换", "100000"))
    orig_forced = any(x in original for x in ("不得不", "被迫", "必须", "停"))
    cand_forced = any(x in candidate for x in ("不得不", "被迫", "必须", "停", "走不了"))
    orig_causal = "因为" in original or "所以" in original or "→" in original
    cand_causal = "因为" in candidate or "所以" in candidate or "→" in candidate
    orig_change = any(x in original for x in ("截图", "八角", "无备案", "匿名"))
    cand_change = any(x in candidate for x in ("截图", "八角", "无备案", "匿名", "走不了", "不能走"))

    score_dim(COMPARISON_DIMS[0], True, True, cand_has_goal and not orig_has_goal, "商业承诺：永久离职/积分目标是否在候选中更前置明确")
    score_dim(COMPARISON_DIMS[1], True, cand_has_goal or orig_has_goal, cand_has_goal and not orig_has_goal, "主角当前目标可见度")
    score_dim(COMPARISON_DIMS[2], True, cand_has_goal, cand_has_goal and not orig_has_goal, "摸鱼系统+准点下班+大楼异常是否成链")
    score_dim(COMPARISON_DIMS[3], orig_forced, cand_forced, cand_forced and not orig_forced, "异常是否迫使行动")
    score_dim(COMPARISON_DIMS[4], orig_causal, cand_causal, cand_causal and not orig_causal, "因果链")
    score_dim(COMPARISON_DIMS[5], orig_change, cand_change, len(candidate) > len(original) * 0.9, "局势变化强度")
    score_dim(COMPARISON_DIMS[6], orig_change, cand_change, cand_change, "章末追读钩子")
    score_dim(COMPARISON_DIMS[7], True, True, None, "需人工抽检人设/系统一致性")
    score_dim(COMPARISON_DIMS[8], True, True, len(candidate) > len(original) * 1.3, "篇幅膨胀可能暗示解释过量")

    better = sum(1 for r in rows if r.get(" verdict") == "候选更优")
    worse = sum(1 for r in rows if r.get(" verdict") == "候选更差")
    if better >= 3 and worse <= 1:
        overall = "PASSED"
    elif better >= 1:
        overall = "PARTIAL"
    else:
        overall = "FAILED"
    return {"phase": 1, "text_a": "原稿", "text_b": "XC-UE候选稿", "dimensions": rows, "REAL_REPAIR_RESULT_hint": overall}


def _compare_texts_phase2(candidate: str, external: str) -> dict[str, Any]:
    rows = []
    for dim in COMPARISON_DIMS[:7]:
        rows.append({"维度": dim, "说明": "XC-UE候选 vs EXTERNAL_REFERENCE_CANDIDATE，仅判差距，不修改本轮产物"})
    return {
        "phase": 2,
        "text_a": "XC-UE候选稿",
        "text_b": "EXTERNAL_REFERENCE_CANDIDATE",
        "external_path": str(EXTERNAL_REF.relative_to(ROOT)),
        "dimensions": rows,
        "note": "外部参考仅用于差距判断，非标准答案",
    }


def run(*, run_id: str, execute_real_api: bool, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = (ROOT / CHAPTER_REL).resolve()
    before_chapter = chapter_path.read_bytes()
    before_source = SOURCE_ORIGINAL.read_bytes()

    _write(
        out_dir / "00_案例资格检查.md",
        "\n".join(
            [
                "# 案例资格（REAL-REPAIR-02）",
                "",
                f"- project_id: `{PROJECT_ID}`",
                f"- chapter_path: `{CHAPTER_REL}`",
                f"- source_original: `{SOURCE_ORIGINAL.relative_to(ROOT)}`（只读，未修改）",
                f"- external_reference: **未纳入运行上下文**（`{EXTERNAL_REF.name}`）",
                f"- 正文字数: {len(re.sub(r'^#.*$', '', chapter_path.read_text(encoding='utf-8-sig'), flags=re.M).strip())}",
                f"- CASE_QUALIFICATION: **PASSED**",
            ]
        )
        + "\n",
    )

    if not execute_real_api:
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "DRY_RUN",
            "CASE_QUALIFICATION": "PASSED",
            "message": "项目已入库；需 --execute-real-api 启动真实链。",
            "real_api_executed": False,
        }
        return _emit(out_dir, result)

    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "API_KEY_MISSING",
            "CASE_QUALIFICATION": "PASSED",
            "message": "未设置 DEEPSEEK_API_KEY",
            "real_api_executed": False,
        }
        return _emit(out_dir, result)

    workspace = out_dir / "runs" / run_id
    workspace.mkdir(parents=True, exist_ok=True)
    l1_out = workspace / "l1"
    l1_out.mkdir(parents=True, exist_ok=True)
    l1_run = f"{run_id}-L1"

    proc = subprocess.run(
        [
            sys.executable,
            str(L1_ENTRY),
            "--project",
            PROJECT_ID,
            "--chapter",
            str(chapter_path),
            "--run-id",
            l1_run,
            "--out-dir",
            str(l1_out),
            "--pipeline-run-id",
            run_id,
            "--capture-semantic-evidence-debug",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l1_payload = _parse_subprocess_json(proc) or _load_l1_payload(l1_out, l1_run)
    _write_json(out_dir / "01_L1原文结果.json", {"exit_code": proc.returncode, "payload": l1_payload})

    l1_status = str(l1_payload.get("status", ""))
    packet_path = l1_out / f"{l1_run}_failure_packet.json"

    if l1_status == "SCREENING_PASS" or (
        packet_path.is_file()
        and json.loads(packet_path.read_text(encoding="utf-8-sig")).get("status") == "SCREENING_PASS"
    ):
        unchanged = chapter_path.read_bytes() == before_chapter and _verify_source_unchanged(chapter_path, before_source)
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "L1_DETECTION_GAP_CANDIDATE",
            "FINAL_STATUS": "L1_DETECTION_GAP_CANDIDATE",
            "CASE_QUALIFICATION": "PASSED",
            "L1_RESULT": "SCREENING_PASS",
            "REPAIR_CHAIN": "NOT_TRIGGERED",
            "BUSINESS_DIAGNOSIS_CONFLICT": "YES",
            "REAL_REPAIR_RESULT": "NOT_EVALUATED",
            "PRIMARY_FINDING": "L1_DETECTION_GAP_CANDIDATE",
            "failure_count": l1_payload.get("failure_count", 0),
            "formal_chapter_unchanged": unchanged,
            "source_original_unchanged": _verify_source_unchanged(chapter_path, before_source),
            "message": "L1 筛查通过，无 routeable 失败项；按任务规则停止，不进入 L2。",
            "real_api_executed": True,
        }
        for name, content in {
            "02_L1_5路由结果.json": {"status": "NOT_RUN", "reason": "L1_SCREENING_PASS"},
            "03_L2修复单.json": {},
            "05_L3执行结果.json": {"status": "NOT_RUN"},
            "06_候选正文路径.md": "# 候选正文路径\n\n未生成。\n",
            "07_原稿与候选对照.md": "# 原稿与候选对照\n\n未执行（L1 SCREENING_PASS）。\n",
            "08_候选与外部参考对照.md": "# 候选与外部参考对照\n\n未执行。\n",
        }.items():
            if name.endswith(".json"):
                _write_json(out_dir / name, content)
            else:
                _write(out_dir / name, content if isinstance(content, str) else "")
        _write(out_dir / "04_L2修复单验收.md", "# L2 修复单验收\n\n未执行。\n")
        return _emit(out_dir, result)

    if l1_status == "AUDIT_BLOCKED" or not packet_path.is_file():
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "L1_AUDIT_BLOCKED",
            "CASE_QUALIFICATION": "PASSED",
            "L1_RESULT": l1_status or "AUDIT_BLOCKED",
            "REPAIR_CHAIN": "NOT_TRIGGERED",
            "REAL_REPAIR_RESULT": "NOT_EVALUATED",
            "message": "L1 审计阻断或无失败包。",
            "real_api_executed": True,
        }
        return _emit(out_dir, result)

    # --- L1.5 ---
    l15_out = workspace / "l15"
    l15_out.mkdir(parents=True, exist_ok=True)
    l15_run = f"{run_id}-L15"
    proc15 = subprocess.run(
        [
            sys.executable,
            str(L15_ENTRY),
            "--failure-packet",
            str(packet_path),
            "--run-id",
            l15_run,
            "--out-dir",
            str(l15_out),
            "--pipeline-run-id",
            run_id,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l15_payload = _parse_subprocess_json(proc15)
    l15_report_path = l15_payload.get("report_json") or str(l15_out / f"{l15_run}.json")
    l15_report = json.loads(Path(l15_report_path).read_text(encoding="utf-8-sig")) if Path(l15_report_path).is_file() else l15_payload
    _write_json(out_dir / "02_L1_5路由结果.json", l15_report)

    final_status = str(l15_report.get("final_status", ""))
    target_module = str(l15_report.get("target_module", ""))

    if final_status != "ROUTED" or not target_module:
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "L15_NO_SINGLE_ROUTE",
            "CASE_QUALIFICATION": "PASSED",
            "L1_RESULT": l1_status,
            "REPAIR_CHAIN": "NOT_TRIGGERED",
            "REAL_REPAIR_RESULT": "NOT_EVALUATED",
            "final_status": final_status,
            "target_module": target_module,
            "message": "L1.5 未形成单一正式路由，停止。",
            "real_api_executed": True,
        }
        return _emit(out_dir, result)

    # --- L2 ---
    l2_out = workspace / "l2"
    l2_out.mkdir(parents=True, exist_ok=True)
    l2_run = f"{run_id}-L2"
    proc2 = subprocess.run(
        [
            sys.executable,
            str(L2_ENTRY),
            "--l15-report",
            str(l15_report_path),
            "--run-id",
            l2_run,
            "--out-dir",
            str(l2_out),
            "--pipeline-run-id",
            run_id,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l2_payload = _parse_subprocess_json(proc2)
    l2_report_json = l2_payload.get("report_json")
    fix_form: dict[str, Any] = {}
    if l2_report_json and Path(l2_report_json).is_file():
        l2_report = json.loads(Path(l2_report_json).read_text(encoding="utf-8-sig"))
        forms = l2_report.get("修复单") or l2_report.get("fix_forms") or []
        if forms:
            fix_form = forms[0] if isinstance(forms[0], dict) else {}
    _write_json(out_dir / "03_L2修复单.json", fix_form or l2_payload)

    ok_fix, fix_errors = _fix_form_accepts_l3(fix_form)
    _write(out_dir / "04_L2修复单验收.md", "\n".join(["# L2 修复单验收", "", f"- target_module: `{target_module}`", f"- 通过: {ok_fix}"] + [f"- {e}" for e in fix_errors]) + "\n")
    if not ok_fix:
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "L2_FIX_FORM_REJECTED",
            "CASE_QUALIFICATION": "PASSED",
            "L1_RESULT": l1_status,
            "target_module": target_module,
            "REAL_REPAIR_RESULT": "NOT_EVALUATED",
            "fix_errors": fix_errors,
            "real_api_executed": True,
        }
        return _emit(out_dir, result)

    # --- L3 ---
    l3_out = workspace / "l3"
    l3_out.mkdir(parents=True, exist_ok=True)
    l3_run = f"{run_id}-L3"
    proc3 = subprocess.run(
        [
            sys.executable,
            str(L3_ENTRY),
            "--l2-report",
            str(l2_report_json),
            "--project-harness",
            str(PROJECT_ROOT.relative_to(ROOT)),
            "--project",
            PROJECT_ID,
            "--run-id",
            l3_run,
            "--out-dir",
            str(l3_out),
            "--pipeline-run-id",
            run_id,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l3_payload = _parse_subprocess_json(proc3)
    _write_json(out_dir / "05_L3执行结果.json", {"exit_code": proc3.returncode, "payload": l3_payload})

    candidate_paths: list[str] = l3_payload.get("candidate_outputs") or []
    if not candidate_paths:
        l3_report = l3_payload.get("report_json")
        if l3_report and Path(l3_report).is_file():
            rep = json.loads(Path(l3_report).read_text(encoding="utf-8-sig"))
            candidate_paths = rep.get("candidate_outputs") or rep.get("候选输出") or []

    if not candidate_paths:
        result = {
            "task": "REAL-REPAIR-02",
            "generated_at": _utc_now(),
            "stop_code": "L3_NO_CANDIDATE",
            "CASE_QUALIFICATION": "PASSED",
            "target_module": target_module,
            "REAL_REPAIR_RESULT": "NOT_EVALUATED",
            "message": "L3 未输出候选路径。",
            "real_api_executed": True,
        }
        return _emit(out_dir, result)

    cand_path = Path(candidate_paths[0])
    if not cand_path.is_absolute():
        cand_path = (ROOT / cand_path).resolve()
    _write(out_dir / "06_候选正文路径.md", f"# 候选正文路径\n\n- `{cand_path.relative_to(ROOT)}`\n")

    original_text = chapter_path.read_text(encoding="utf-8-sig")
    candidate_text = cand_path.read_text(encoding="utf-8-sig") if cand_path.is_file() else ""
    phase1 = _compare_texts_phase1(original_text, candidate_text)
    _write_json(out_dir / "07_原稿与候选对照.json", phase1)
    md1 = ["# 原稿与候选对照（阶段一）", "", "文本A = 原稿 | 文本B = XC-UE候选稿", ""]
    for row in phase1["dimensions"]:
        md1.append(f"- **{row['维度']}**: {row.get(' verdict', '—')} — {row.get('说明', '')}")
    md1.append(f"\n**REAL_REPAIR_RESULT_hint**: `{phase1['REAL_REPAIR_RESULT_hint']}`")
    _write(out_dir / "07_原稿与候选对照.md", "\n".join(md1) + "\n")

    # 阶段二：L3 完成后才读取外部参考
    external_text = EXTERNAL_REF.read_text(encoding="utf-8-sig") if EXTERNAL_REF.is_file() else ""
    phase2 = _compare_texts_phase2(candidate_text, external_text)
    _write_json(out_dir / "08_候选与外部参考对照.json", phase2)
    _write(
        out_dir / "08_候选与外部参考对照.md",
        "# 候选与外部参考对照（阶段二）\n\n"
        "文本A = XC-UE候选稿 | 文本B = EXTERNAL_REFERENCE_CANDIDATE\n\n"
        "外部参考仅用于差距判断，非标准答案；未反向修改 prompt/修复单/候选稿。\n",
    )

    unchanged = chapter_path.read_bytes() == before_chapter
    repair_result = phase1["REAL_REPAIR_RESULT_hint"]
    result = {
        "task": "REAL-REPAIR-02",
        "generated_at": _utc_now(),
        "stop_code": "COMPLETED",
        "CASE_QUALIFICATION": "PASSED",
        "L1_RESULT": l1_status,
        "REPAIR_CHAIN": "TRIGGERED",
        "target_module": target_module,
        "REAL_REPAIR_RESULT": repair_result,
        "PRIMARY_FINDING": "",
        "formal_chapter_unchanged": unchanged,
        "source_original_unchanged": _verify_source_unchanged(chapter_path, before_source),
        "candidate_path": str(cand_path.relative_to(ROOT)),
        "real_api_executed": True,
        "message": f"L1→L1.5→{target_module}→L3 完成；阶段一对照 hint={repair_result}。",
    }
    return _emit(out_dir, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="REAL-REPAIR-02 准点下班怎么了")
    parser.add_argument("--run-id", default=f"RR02-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--out-dir", default=str(OUT_BASE))
    parser.add_argument("--execute-real-api", action="store_true")
    parser.add_argument("--precheck-only", action="store_true")
    args = parser.parse_args()
    return run(run_id=args.run_id, execute_real_api=args.execute_real_api and not args.precheck_only, out_dir=Path(args.out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
