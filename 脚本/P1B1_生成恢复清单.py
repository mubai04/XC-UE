#!/usr/bin/env python3
"""P1B-1：从 P1A 盘点结果生成历史误删恢复清单（只读分析）。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "00_工程总控" / "Git工作树治理_20260628"
REC = INV / "P1B1_执行记录"
DETAIL = INV / "02_全部变更明细.json"

DEPRECATED_STATUS = {
    "XC-UE_全量深度盘查报告_2026-06-27.md",
}

RESTORE_TAGS = {"KEEP_TRACKED_HISTORY", "POSSIBLE_ACCIDENTAL_DELETE"}


def main() -> None:
    entries = json.loads(DETAIL.read_text(encoding="utf-8-sig"))
    restore: list[str] = []
    skipped: list[tuple[str, str]] = []

    rename_old_paths = {
        e.get("old_path", "").replace("\\", "/")
        for e in entries
        if e.get("kind") == "renamed" and e.get("old_path")
    }
    rename_new_paths = {
        e.get("path", "").replace("\\", "/")
        for e in entries
        if e.get("kind") == "renamed" and e.get("path")
    }

    for e in entries:
        path = (e.get("path") or e.get("old_path") or "").replace("\\", "/")
        if not path:
            continue
        is_delete = e.get("kind") == "deleted" or e.get("worktree_status") == "D" or e.get("index_status") == "D"
        if not is_delete:
            continue
        tags = set(e.get("risk_tags") or [])
        reasons: list[str] = []

        if path.startswith("运行记录/"):
            skipped.append((path, "运行记录待裁决"))
            continue
        if "RENAME_PAIR" in tags or path in rename_old_paths:
            skipped.append((path, "重命名旧路径"))
            continue
        if path in rename_new_paths:
            skipped.append((path, "已有替代文件"))
            continue
        if Path(path).name in DEPRECATED_STATUS or "STALE_STATUS" in tags and "POSSIBLE_ACCIDENTAL_DELETE" not in tags:
            if Path(path).name in DEPRECATED_STATUS:
                skipped.append((path, "明确废弃候选"))
                continue
        if not (RESTORE_TAGS & tags):
            skipped.append((path, "信息不足或未命中恢复标签"))
            continue
        restore.append(path)

    restore = sorted(set(restore))
    REC.mkdir(parents=True, exist_ok=True)
    (REC / "恢复清单_历史误删.txt").write_text("\n".join(restore) + ("\n" if restore else ""), encoding="utf-8")

    lines = ["# 未恢复删除项清单", "", f"恢复：**{len(restore)}**", f"跳过：**{len(skipped)}**", ""]
    by_reason: dict[str, list[str]] = {}
    for p, r in skipped:
        by_reason.setdefault(r, []).append(p)
    for reason, paths in sorted(by_reason.items()):
        lines.append(f"## {reason}（{len(paths)}）")
        lines.append("")
        for p in paths[:50]:
            lines.append(f"- `{p}`")
        if len(paths) > 50:
            lines.append(f"- … 另有 {len(paths) - 50} 项")
        lines.append("")
    (REC / "未恢复删除项清单.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"RESTORE_CANDIDATES={len(restore)}")
    print(f"SKIPPED={len(skipped)}")


if __name__ == "__main__":
    main()
