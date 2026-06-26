from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import pytest

from DeepSeek客户端 import DeepSeekClient
from L1_语义审计 import 审计
from 正文切分 import 切段, 清理正文
from tests.conftest import ROOT, make_mock_transport, sample_chapter_text


@pytest.fixture
def external_io_token(tmp_path, monkeypatch):
    token_file = tmp_path / "io.token"
    token_file.write_text("XCUE_TEST_EXTERNAL_IO_TOKEN_V1", encoding="utf-8")
    monkeypatch.setenv("XCUE_TEST_ALLOW_EXTERNAL_IO", "1")
    monkeypatch.setenv("XCUE_TEST_IO_TOKEN_FILE", str(token_file))
    return token_file


def _load_subprocess_json(result: subprocess.CompletedProcess) -> dict:
    for stream in (result.stdout, result.stderr):
        text = (stream or "").strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
    raise AssertionError(f"no JSON payload: stdout={result.stdout!r} stderr={result.stderr!r}")


def test_l1_entry_semantic_unavailable_rejects(external_io_token, tmp_path):
    seed = uuid.uuid4().hex[:8]
    chapter = tmp_path / f"{seed}.md"
    chapter.write_text(sample_chapter_text(seed), encoding="utf-8")
    run_id = f"E2E-L1-{seed}"
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    cmd = [
        sys.executable,
        str(ROOT / "00_工程总控" / "工程执行层" / "L1工程" / "L1运行入口.py"),
        "--run-id",
        run_id,
        "--chapter",
        str(chapter),
        "--out-dir",
        str(tmp_path / "reports"),
        "--project",
        "pytest",
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", env=env)
    assert result.returncode != 0, result.stdout + result.stderr
    payload = _load_subprocess_json(result)
    assert payload.get("status") != "SCREENING_PASS"
    assert payload.get("exit_code", result.returncode) != 0


def test_l1_inprocess_semantic_mock_passes():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    quote = f"{seed} 忽然察觉异常"
    payload = {
        "overall": "PASS",
        "dimensions": [
            {
                "name": name,
                "verdict": "PASS",
                "score": 4,
                "explanation": "ok",
                "evidence_quotes": [{"paragraph": 1, "quote": quote}],
            }
            for name in ("因果", "动机", "冲突", "读者收益", "认知成本", "章末追读")
        ],
    }
    client = DeepSeekClient(api_key="k", transport=make_mock_transport(payload))
    result = 审计(paragraphs, title, body, client=client)
    assert result.可用
    assert result.整体结论 == "PASS"
