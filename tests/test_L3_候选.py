from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from DeepSeek客户端 import create_client
from L3模型 import L3执行任务
from 候选正文生成 import 生成候选正文
from 输出生成 import 生成输出
from tests.conftest import make_mock_transport, repo_root


def _task(seed: str, harness_rel: str, target_rel: str) -> L3执行任务:
    return L3执行任务(
        执行编号=f"L3RUN-{seed}-001",
        来源层="L2-05",
        来源文件="运行记录/mock/第二层/report.json",
        ProjectHarness根=harness_rel,
        任务类型="正文局部修复任务规划",
        输入材料=f"{seed} 读者收益不足",
        IR输入=[f"{harness_rel}/IR/IR-00_项目索引.md"],
        目标文件=target_rel,
        禁止修改文件=[f"{harness_rel}/chapters/ch01.md"],
        修复方向="增强章末追读钩子",
        修复产物要求="候选正文",
        回流验收位置="L1-02",
        是否允许改正式正文="否",
        是否需要备份="不适用",
    )


def _make_harness(repo_root: Path, seed: str) -> Path:
    harness = repo_root / "运行记录" / f"pytest-{seed}"
    if harness.exists():
        shutil.rmtree(harness)
    (harness / "IR").mkdir(parents=True)
    (harness / "chapters" / "_candidates").mkdir(parents=True)
    (harness / "logs").mkdir()
    (harness / "IR" / "IR-00_项目索引.md").write_text("# IR\n", encoding="utf-8")
    (harness / "chapters" / "ch01.md").write_text(f"# ch\n\n{seed} 正式正文。\n", encoding="utf-8")
    return harness


def test_candidate_only_under_candidates(repo_root):
    seed = uuid.uuid4().hex[:8]
    harness = _make_harness(repo_root, seed)
    try:
        rel_h = harness.relative_to(repo_root).as_posix()
        bad = _task(seed, rel_h, f"{rel_h}/chapters/ch02.md")
        bad_result = 生成候选正文(bad, harness, repo_root, client=create_client("L3", api_key="k"))
        assert not bad_result.ok
        assert bad_result.error_kind == "PATH_FORBIDDEN"

        target = f"{rel_h}/chapters/_candidates/{seed}_TASK-001.md"
        task = _task(seed, rel_h, target)
        body = f"{seed} 新段落一。\n\n{seed} 新段落二，冲突继续升级。\n"
        payload = {"title": f"候选 {seed}", "body": body}
        client = create_client("L3", api_key="k", transport=make_mock_transport(payload))
        ok = 生成候选正文(task, harness, repo_root, client=client)
        assert ok.ok
        assert ok.path is not None
        assert "_candidates" in str(ok.path)
    finally:
        shutil.rmtree(harness, ignore_errors=True)


def test_candidate_api_failure_blocks_task(repo_root):
    seed = uuid.uuid4().hex[:8]
    harness = _make_harness(repo_root, seed)
    try:
        rel_h = harness.relative_to(repo_root).as_posix()
        target = f"{rel_h}/chapters/_candidates/{seed}_TASK-002.md"
        task = _task(seed, rel_h, target)
        output = 生成输出(task, repo_root, harness_root=harness, client=create_client("L3", api_key=""))
        assert output.执行状态 == "CANDIDATE_FAILED"
        assert output.task_package_created
        assert not output.candidate_created
        assert not output.awaiting_executor
        assert not (repo_root / target).exists()
    finally:
        shutil.rmtree(harness, ignore_errors=True)
