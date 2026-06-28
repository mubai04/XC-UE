#!/usr/bin/env python3
"""L2-01 单章节真实结构修复闭环编排（L2-01-REAL-01）。

仅调用既有 L1 / L1.5 / L2 / L3 正式入口；不复制领域逻辑。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "审计纠偏_2026-06-26" / "L2_01单模块真实修复_20260628"
EXEC = ROOT / "00_工程总控" / "工程执行层"
L1_ENTRY = EXEC / "L1工程" / "L1运行入口.py"
L15_ENTRY = EXEC / "L1.5工程" / "L1.5运行入口.py"
L2_ENTRY = EXEC / "L2工程" / "L2运行入口.py"
L3_ENTRY = EXEC / "L3工程" / "L3运行入口.py"
PIPELINE_ENTRY = EXEC / "修复流水线运行入口.py"

sys.path.insert(0, str(ROOT / "脚本"))
from L2_01真实修复_案例资格 import 扫描全部案例, 校验指定案例, 资格结果  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_main(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _chapter_bytes(chapter: Path) -> bytes:
    return chapter.read_bytes()


def _compare_formal_unchanged(before: bytes, chapter: Path) -> bool:
    return chapter.read_bytes() == before


def _fix_form_accepts_l3(fix: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = (
        "模块内主问题", "根因", "修复规则", "修复动作", "禁止修改范围",
        "必须保留内容", "验收条件", "修复单状态",
    )
    for key in required:
        if key not in fix and key.replace("模块内", "") not in str(fix):
            # 兼容 dataclass 中文键与可能的英文迁移
            if key not in fix:
                errors.append(f"缺少字段：{key}")
    actions = fix.get("修复动作") or fix.get("fix_actions") or []
    if not actions:
        errors.append("修复动作为空")
    else:
        vague = ("加强结构", "优化节奏", "提升质量")
        if all(any(v in str(a) for v in vague) for a in actions):
            errors.append("修复动作过于空泛")
    status = str(fix.get("修复单状态", ""))
    if status and status not in ("READY_FOR_L3", "允许进入L3", "READY"):
        errors.append(f"修复单状态不允许进入 L3：{status}")
    reroute = fix.get("重路由请求") or {}
    if isinstance(reroute, dict) and reroute.get("禁止直接指定新目标模块") is False:
        errors.append("重路由请求允许直接指定新目标模块")
    return not errors, errors


def _emit_stop(out_dir: Path, result: dict[str, Any]) -> int:
    _write_json(out_dir / "L2_01单模块真实修复结果.json", result)
    _write(
        out_dir / "10_最终业务结论.md",
        "\n".join(
            [
                "# 最终业务结论",
                "",
                f"- **停止码**：`{result.get('stop_code', '')}`",
                f"- **业务状态**：`{result.get('business_status', '')}`",
                f"- **说明**：{result.get('message', '')}",
                "",
                "## 后续",
                "",
                result.get("next_step", "等待合格真实章节入库后再执行。"),
            ]
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    code = result.get("stop_code", "")
    if code in ("REAL_L2_01_CASE_REQUIRED", "CASE_NOT_ROUTED_TO_L2_01", "L2_01_FIX_FORM_REJECTED", "L3_RESULT_INCONSISTENT"):
        return 2
    return 0 if result.get("business_status") == "PASSED" else 3


def _record_case_manifest(out_dir: Path, qual: 资格结果, chapter: Path, before: bytes) -> None:
    cand = qual.candidate
    md = [
        "# 案例资格与冻结输入",
        "",
        f"- generated_at: {_utc_now()}",
        f"- 合格: **{qual.ok}**",
        f"- stop_code: `{qual.stop_code or '—'}`",
    ]
    if cand:
        md.extend(
            [
                f"- project_id: `{cand.project_id}`",
                f"- chapter_path: `{cand.chapter_path}`",
                f"- chapter_sequence_index: {cand.chapter_sequence_index}",
                f"- 原始章节只读声明: **是**（运行前后逐字节比对）",
                f"- 冻结前字节长度: {len(before)}",
            ]
        )
    md.extend(["", "## 扫描摘要", "", f"共扫描 {len(qual.scanned)} 个候选。"])
    if qual.missing:
        md.append("")
        md.append("## 缺少条件")
        md.extend(f"- {m}" for m in qual.missing)
    if qual.scanned:
        md.append("")
        md.append("## 扫描明细（节选）")
        for row in qual.scanned[:10]:
            md.append(f"- `{row.get('chapter_path', row.get('project_id', '?'))}` → {row.get('reasons', row.get('error', []))}")
    _write(out_dir / "00_案例资格检查.md", "\n".join(md) + "\n")


def run(*, project_id: str | None, chapter: str | None, run_id: str, execute_real_api: bool, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    qual = 校验指定案例(project_id, chapter, ROOT) if project_id and chapter else 扫描全部案例(ROOT)

    if not qual.ok:
        _record_case_manifest(out_dir, qual, Path("."), b"")
        placeholders = {
            "05_L3执行结果.json": {"status": "NOT_RUN", "reason": qual.stop_code},
            "06_候选正文路径.md": "# 候选正文路径\n\n未生成（案例不合格）。\n",
            "07_L1候选复验.json": {"status": "NOT_RUN"},
            "08_原文与候选对照报告.md": "# 原文与候选对照报告\n\n未执行。\n",
            "09_匿名顺序交换评估.json": {"status": "NOT_RUN"},
        }
        for name, content in placeholders.items():
            if name.endswith(".json"):
                _write_json(out_dir / name, content)
            else:
                _write(out_dir / name, content if isinstance(content, str) else "")
        result = {
            "task": "L2-01-REAL-01",
            "generated_at": _utc_now(),
            "stop_code": qual.stop_code,
            "business_status": "INVALID_CASE",
            "message": qual.message,
            "missing": qual.missing,
            "scanned_count": len(qual.scanned),
            "real_api_executed": False,
            "next_step": "在 00_工程总控/工程执行层/项目注册表.json 登记真实小说项目并写入完整章节后再运行。",
        }
        return _emit_stop(out_dir, result)

    assert qual.candidate is not None
    chapter_path = (ROOT / qual.candidate.chapter_path).resolve()
    before = _chapter_bytes(chapter_path)
    _record_case_manifest(out_dir, qual, chapter_path, before)

    if not execute_real_api:
        result = {
            "task": "L2-01-REAL-01",
            "generated_at": _utc_now(),
            "stop_code": "DRY_RUN_QUALIFIED",
            "business_status": "PENDING_REAL_API",
            "project_id": qual.candidate.project_id,
            "chapter_path": qual.candidate.chapter_path,
            "formal_chapter_unchanged": True,
            "message": "案例资格已通过；需 --execute-real-api 启动真实 API 链。",
            "real_api_executed": False,
        }
        _write_json(out_dir / "L2_01单模块真实修复结果.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        result = {
            "task": "L2-01-REAL-01",
            "generated_at": _utc_now(),
            "stop_code": "API_KEY_MISSING",
            "business_status": "INVALID_CASE",
            "message": "未设置 DEEPSEEK_API_KEY，无法执行真实 API。",
            "real_api_executed": False,
        }
        return _emit_stop(out_dir, result)

    print("REAL_API_CALLS_PLANNED:")
    for line in (
        "- L1原文",
        "- L2-01修复单",
        "- L3候选生成",
        "- L1候选复验",
        "- 匿名比较A/B",
        "- 匿名比较B/A",
    ):
        print(line)

    workspace = out_dir / "runs" / run_id
    workspace.mkdir(parents=True, exist_ok=True)
    l1_out = workspace / "l1_original"
    l1_out.mkdir(parents=True, exist_ok=True)

    # --- L1 原文 ---
    l1_run = f"{run_id}-L1-ORIG"
    proc = subprocess.run(
        [
            sys.executable,
            str(L1_ENTRY),
            "--project",
            qual.candidate.project_id,
            "--chapter",
            str(chapter_path),
            "--run-id",
            l1_run,
            "--out-dir",
            str(l1_out),
            "--pipeline-run-id",
            run_id,
            "--stage-run-id",
            f"{run_id}-L1",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l1_payload = {}
    for stream in (proc.stdout, proc.stderr):
        for line in reversed((stream or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    l1_payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    if not l1_payload:
        for report_json in sorted(l1_out.glob("*.json")):
            if any(x in report_json.name for x in ("_failure_packet", "_audit_blockers")):
                continue
            try:
                l1_payload = json.loads(report_json.read_text(encoding="utf-8-sig"))
                break
            except (OSError, json.JSONDecodeError):
                continue
    _write_json(out_dir / "01_L1原文结果.json", {"exit_code": proc.returncode, "payload": l1_payload, "stdout_tail": (proc.stdout or "")[-4000:]})

    l1_status = str(l1_payload.get("status", ""))
    packet_path = l1_out / f"{l1_run}_failure_packet.json"
    if not l1_status and packet_path.is_file():
        try:
            l1_status = str(json.loads(packet_path.read_text(encoding="utf-8-sig")).get("status", ""))
        except (OSError, json.JSONDecodeError):
            pass
    if l1_status == "AUDIT_BLOCKED" or not packet_path.is_file():
        result = {
            "task": "L2-01-REAL-01",
            "stop_code": "L1_AUDIT_BLOCKED",
            "business_status": "INVALID_CASE",
            "l1_status": l1_status,
            "message": "L1 AUDIT_BLOCKED 或无失败包，停止。",
            "real_api_executed": True,
        }
        return _emit_stop(out_dir, result)
    if l1_status == "SCREENING_PASS":
        result = {
            "task": "L2-01-REAL-01",
            "stop_code": "L1_SCREENING_PASS",
            "business_status": "INVALID_CASE",
            "message": "SCREENING_PASS 不得进入修复链。",
            "real_api_executed": True,
        }
        return _emit_stop(out_dir, result)

    # --- L1.5 ---
    l15_out = workspace / "l15"
    l15_out.mkdir(parents=True, exist_ok=True)
    l15_run = f"{run_id}-L15"
    proc15 = subprocess.run(
        [sys.executable, str(L15_ENTRY), "--failure-packet", str(packet_path), "--run-id", l15_run, "--out-dir", str(l15_out), "--pipeline-run-id", run_id],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l15_payload = {}
    for stream in (proc15.stdout, proc15.stderr):
        for line in reversed((stream or "").splitlines()):
            if line.strip().startswith("{"):
                try:
                    l15_payload = json.loads(line.strip())
                    break
                except json.JSONDecodeError:
                    continue
    l15_report_path = l15_payload.get("report_json") or str(l15_out / f"{l15_run}.json")
    l15_report = json.loads(Path(l15_report_path).read_text(encoding="utf-8-sig")) if Path(l15_report_path).is_file() else l15_payload
    _write_json(out_dir / "02_L1_5路由结果.json", l15_report)

    if str(l15_report.get("final_status")) != "ROUTED" or str(l15_report.get("target_module")) != "L2-01":
        result = {
            "task": "L2-01-REAL-01",
            "stop_code": "CASE_NOT_ROUTED_TO_L2_01",
            "business_status": "INVALID_CASE",
            "target_module": l15_report.get("target_module"),
            "final_status": l15_report.get("final_status"),
            "message": "L1.5 未自然路由至 L2-01，停止。",
            "real_api_executed": True,
        }
        return _emit_stop(out_dir, result)

    # --- L2 ---
    l2_out = workspace / "l2"
    l2_out.mkdir(parents=True, exist_ok=True)
    l2_run = f"{run_id}-L2"
    proc2 = subprocess.run(
        [sys.executable, str(L2_ENTRY), "--l15-report", str(l15_report_path), "--run-id", l2_run, "--out-dir", str(l2_out), "--pipeline-run-id", run_id],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    l2_payload = {}
    for stream in (proc2.stdout, proc2.stderr):
        for line in reversed((stream or "").splitlines()):
            if line.strip().startswith("{"):
                try:
                    l2_payload = json.loads(line.strip())
                    break
                except json.JSONDecodeError:
                    continue
    l2_report_json = l2_payload.get("report_json")
    fix_form = {}
    if l2_report_json and Path(l2_report_json).is_file():
        l2_report = json.loads(Path(l2_report_json).read_text(encoding="utf-8-sig"))
        forms = l2_report.get("修复单") or l2_report.get("fix_forms") or []
        if forms:
            fix_form = forms[0] if isinstance(forms[0], dict) else forms[0].__dict__ if hasattr(forms[0], "__dict__") else {}
    _write_json(out_dir / "03_L2_01修复单.json", fix_form or l2_payload)

    ok_fix, fix_errors = _fix_form_accepts_l3(fix_form)
    _write(out_dir / "04_L2修复单验收.md", "\n".join(["# L2 修复单验收", "", f"- 通过: {ok_fix}"] + [f"- {e}" for e in fix_errors]) + "\n")
    if not ok_fix:
        result = {
            "task": "L2-01-REAL-01",
            "stop_code": "L2_01_FIX_FORM_REJECTED",
            "business_status": "CALIBRATION_REQUIRED",
            "fix_errors": fix_errors,
            "real_api_executed": True,
        }
        return _emit_stop(out_dir, result)

    # --- L3 via repair pipeline remainder would go here; abbreviated for qualified+api path ---
    unchanged = _compare_formal_unchanged(before, chapter_path)
    business = "CALIBRATION_REQUIRED" if unchanged else "INVALID_CASE"
    result = {
        "task": "L2-01-REAL-01",
        "generated_at": _utc_now(),
        "stop_code": "PIPELINE_PARTIAL",
        "business_status": business,
        "project_id": qual.candidate.project_id,
        "chapter_path": qual.candidate.chapter_path,
        "formal_chapter_unchanged": unchanged,
        "l1_status": l1_status,
        "target_module": "L2-01",
        "real_api_executed": True,
        "message": "L1/L1.5/L2 已执行；L3/对照/复验需案例完整闭环后继续。",
    }
    return _emit_stop(out_dir, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="L2-01 单章节真实结构修复闭环")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--chapter", default=None, help="章节相对路径")
    parser.add_argument("--run-id", default=f"L2R01-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--out-dir", default=str(OUT_BASE))
    parser.add_argument("--execute-real-api", action="store_true", help="执行真实 API（需 DEEPSEEK_API_KEY）")
    parser.add_argument("--precheck-only", action="store_true", help="仅案例资格检查")
    args = parser.parse_args()

    if args.precheck_only:
        args.execute_real_api = False

    return run(
        project_id=args.project_id,
        chapter=args.chapter,
        run_id=args.run_id,
        execute_real_api=args.execute_real_api,
        out_dir=Path(args.out_dir),
    )


if __name__ == "__main__":
    raise SystemExit(main())
