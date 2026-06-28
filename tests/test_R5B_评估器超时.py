from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_eval():
    import importlib.util
    import sys

    path = ROOT / "脚本" / "评估_L2_真实API试跑.py"
    spec = importlib.util.spec_from_file_location("eval_l2_real_api_pilot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_rules(module_id: str):
    return SimpleNamespace(能力规则={module_id: object()})


def _entry(module_id: str = "L2-02") -> dict:
    return {"case_id": "X", "target_module": module_id, "case_dir": "cases/L2P-003"}


def _fake_item(mod):
    return mod.失败输入(
        来源闸门="L1-01",
        名称="x",
        状态="失败",
        说明="x",
        证据=[],
        严重级别="error",
        失败类型="文风失败",
        候选模块="L2-02",
        回流验收位置="L1-01",
        修复方向="x",
    )


def _ok_form(mod):
    return mod.修复单(
        修复单类型="t",
        来源闸门="L1-01",
        接收模块="L2-02",
        输入问题="x",
        主失败类型="x",
        次失败类型="",
        修复动作="a",
        修复产物="p",
        验收问题="q",
        回流位置="L1-01",
        是否需要其他L2辅助="否",
        是否需要回L15重路由="否",
        最终状态="回原闸门复验",
    )


def test_cli_timeout_passed_to_client(monkeypatch):
    mod = _load_eval()
    captured: list[float] = []
    real_create = mod.create_client

    def fake_create(stage, **kwargs):
        client = real_create(stage, api_key="k", timeout=kwargs.get("timeout"))
        captured.append(float(client.request_timeout_seconds))
        return client

    monkeypatch.setattr(mod, "create_client", fake_create)
    monkeypatch.setattr(mod, "_load_failure_item", lambda _d: _fake_item(mod))
    monkeypatch.setitem(mod.GENERATORS, "L2-02", lambda *a, **k: (_ok_form(mod), None))
    mod.run_single_case(_entry(), _fake_rules("L2-02"), max_tokens=100, request_timeout=180.0)
    assert captured == [180.0]


def test_env_timeout_override(monkeypatch):
    mod = _load_eval()
    captured: list[float] = []
    real_create = mod.create_client

    def fake_create(stage, **kwargs):
        client = real_create(stage, api_key="k", timeout=kwargs.get("timeout"))
        captured.append(float(client.request_timeout_seconds))
        return client

    monkeypatch.setenv("XCUE_L2_REQUEST_TIMEOUT", "240")
    monkeypatch.setattr(mod, "create_client", fake_create)
    monkeypatch.setattr(mod, "_load_failure_item", lambda _d: _fake_item(mod))
    monkeypatch.setitem(mod.GENERATORS, "L2-02", lambda *a, **k: (_ok_form(mod), None))
    mod.run_single_case(_entry(), _fake_rules("L2-02"), max_tokens=100, request_timeout=None)
    assert captured == [240.0]


def test_read_timeout_retries_once(monkeypatch):
    mod = _load_eval()
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return None, "L2-02 TIMEOUT: The read operation timed out"
        return mod.修复单(
            修复单类型="t",
            来源闸门="L1-01",
            接收模块="L2-02",
            输入问题="x",
            主失败类型="x",
            次失败类型="",
            修复动作="a",
            修复产物="p",
            验收问题="q",
            回流位置="L1-01",
            是否需要其他L2辅助="否",
            是否需要回L15重路由="否",
            最终状态="回原闸门复验",
        ), None

    monkeypatch.setitem(mod.GENERATORS, "L2-02", flaky)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(mod, "_load_failure_item", lambda _d: _fake_item(mod))
    attempts, _ = mod.run_single_case(_entry(), _fake_rules("L2-02"), max_tokens=100, request_timeout=180.0)
    assert len(attempts) == 2
    assert attempts[0].attempt == 1
    assert attempts[1].attempt == 2
    assert attempts[-1].repair_form is not None


def test_read_timeout_stops_after_second_failure(monkeypatch):
    mod = _load_eval()

    def always_timeout(*a, **k):
        return None, "L2-02 TIMEOUT: The read operation timed out"

    monkeypatch.setitem(mod.GENERATORS, "L2-02", always_timeout)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(mod, "_load_failure_item", lambda _d: _fake_item(mod))
    attempts, stop = mod.run_single_case(_entry(), _fake_rules("L2-02"), max_tokens=100, request_timeout=180.0)
    assert len(attempts) == 2
    assert attempts[0].transport_status == "READ_TIMEOUT"
    assert attempts[1].transport_status == "READ_TIMEOUT"
    assert stop is None


def test_auth_error_no_retry(monkeypatch):
    mod = _load_eval()

    def auth_fail(*a, **k):
        return None, "L2-02 MISSING_API_KEY: 缺少 DEEPSEEK_API_KEY"

    monkeypatch.setitem(mod.GENERATORS, "L2-02", auth_fail)
    monkeypatch.setattr(mod, "_load_failure_item", lambda _d: _fake_item(mod))
    attempts, stop = mod.run_single_case(_entry(), _fake_rules("L2-02"), max_tokens=100, request_timeout=180.0)
    assert len(attempts) == 1
    assert stop == "AUTH_ERROR"
