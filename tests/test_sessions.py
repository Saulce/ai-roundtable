# tests/test_sessions.py
import asyncio
import json
import pytest

from app.personas import PRESET_PERSONAS
from app.sessions import SessionManager
from app.storage import Storage


def _handler(prompt):
    if "下一发言" in prompt:
        return json.dumps({"next_speaker": "杠精", "stalled": False})
    if "开场立场陈述" in prompt:
        return "开场。"
    if "发言一次" in prompt:
        return ["发", "言", "。"]
    if "分段摘要" in prompt:
        return "## 本段焦点\n..."
    return "## 脉络概述\n..."


@pytest.fixture
def sm(tmp_path, fake_llm):
    llm = fake_llm(_handler)
    storage = Storage(str(tmp_path / "s.db"))
    return SessionManager(llm, storage, default_max_turns=3)


def test_create_persists_and_returns_id(sm):
    did = sm.create("话题", PRESET_PERSONAS[:3], None)
    assert did
    assert sm.storage.get_discussion(did)["topic"] == "话题"
    assert sm.storage.get_discussion(did)["max_turns"] == 3  # 默认


def test_run_pauses_at_default_turn_limit(sm):
    did = sm.create("话题", PRESET_PERSONAS[:3], None)
    events = sm._run_sync(did)
    types = [e["type"] for e in events]
    assert types.count("message") == 3
    assert types[-1] == "paused"
    assert sm.storage.get_discussion(did)["status"] == "paused"


def test_continue_runs_another_segment(sm):
    did = sm.create("话题", PRESET_PERSONAS[:3], None)
    sm._run_sync(did)                    # 3 轮 → 暂停
    sm.continue_(did)
    events = sm._run_sync(did)           # 再 3 轮
    types = [e["type"] for e in events]
    assert types.count("opening") == 0   # 不重复开场
    assert types.count("message") == 3
    assert len(sm.storage.get_discussion(did)["messages"]) == 9  # 3 开场 + 6 发言


def test_stop_triggers_final_summary(sm):
    did = sm.create("话题", PRESET_PERSONAS[:3], None)
    sm._run_sync(did)
    ev = asyncio.run(sm.stop(did))
    assert ev["type"] == "terminated"
    assert sm.storage.get_discussion(did)["status"] == "terminated"
    assert any(s["mode"] == "final" for s in sm.storage.get_discussion(did)["summaries"])
