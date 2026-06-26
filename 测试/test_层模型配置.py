from __future__ import annotations

import os

from DeepSeek客户端 import create_client


def test_env_model_overrides():
    os.environ["XCUE_L1_MODEL"] = "custom-l1-model"
    try:
        client = create_client("L1", api_key="k")
        assert client.model == "custom-l1-model"
        assert client.stage == "L1"
    finally:
        os.environ.pop("XCUE_L1_MODEL", None)
