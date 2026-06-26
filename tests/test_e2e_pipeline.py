from __future__ import annotations

import uuid

from DeepSeek客户端 import create_client
from L1_语义审计 import 审计
from 正文切分 import 切段, 清理正文
from tests.conftest import make_mock_transport, sample_chapter_text, semantic_audit_payload


def test_l1_inprocess_semantic_mock_passes():
    seed = uuid.uuid4().hex[:8]
    text = sample_chapter_text(seed)
    title, body = 清理正文(text)
    paragraphs = 切段(body)
    quote = f"{seed} 忽然察觉异常"
    client = create_client("L1", api_key="k", transport=make_mock_transport(semantic_audit_payload(quote, overall="PASS")))
    result = 审计(paragraphs, title, body, client=client)
    assert result.可用
    assert result.整体结论 == "PASS"
