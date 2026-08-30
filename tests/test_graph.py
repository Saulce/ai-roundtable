import asyncio
import json

from app.graph import build_graph, should_end
from app.personas import PRESET_PERSONAS


def _base_state(max_turns=3):
    return {
        "topic": "是否应该禁止未成年人使用手机",
        "personas": [p.model_dump() for p in PRESET_PERSONAS[:3]],
        "opening_statements": [],
        "transcript": [],
        "next_speaker": "",
        "stalled": False,
        "turn_count": 0,
        "max_turns": max_turns,
        "segment_start": 0,
        "status": "running",
        "mode": "",
        "summary": "",
    }


def test_should_end_at_turn_limit():
    st = _base_state()
    st["turn_count"] = 3
    assert should_end(st) == "summarize"


def test_should_end_continues_before_limit():
    st = _base_state()
    st["turn_count"] = 2
    assert should_end(st) == "select_speaker"


def test_should_end_unlimited_never_pauses_by_turns():
    st = _base_state(max_turns=0)
    st["turn_count"] = 999
    assert should_end(st) == "select_speaker"


def test_graph_runs_opening_then_speeches_and_pauses(fake_llm):
    def handler(prompt):
        if "下一发言" in prompt:
            return json.dumps({"next_speaker": "杠精", "stalled": False})
        if "开场立场陈述" in prompt:
            return "这是开场陈述。"
        if "发言一次" in prompt:
            return ["这", "是", "自", "由", "发", "言", "。"]
        return "## 本段焦点\n..."
    llm = fake_llm(handler)
    graph = build_graph(llm)

    events = asyncio.run(_collect(graph, _base_state()))
    types = [e["type"] for e in events]
    assert types.count("opening") == 3          # 3 个角色各一条开场
    assert types.count("message") == 3          # 3 轮自由发言（max_turns=3）
    assert types.count("token") == 3 * 7        # 每条发言 7 个 token
    assert types[-1] == "paused"                # 达上限 → 暂停 → 分段摘要


def test_graph_skips_opening_when_already_present(fake_llm):
    def handler(prompt):
        if "下一发言" in prompt:
            return json.dumps({"next_speaker": "杠精", "stalled": False})
        if "发言一次" in prompt:
            return ["再", "说", "一", "句", "。"]
        return "## 本段焦点\n..."
    llm = fake_llm(handler)
    graph = build_graph(llm)
    st = _base_state(max_turns=1)
    st["opening_statements"] = [{"speaker": "好为人师者", "content": "开场。", "kind": "opening"}]
    st["turn_count"] = 3

    events = asyncio.run(_collect(graph, st))
    types = [e["type"] for e in events]
    assert types.count("opening") == 0          # 已开场 → 跳过
    assert types.count("message") == 1


async def _collect(graph, state):
    out = []
    async for ev in graph.astream(state, stream_mode="custom"):
        out.append(ev)
    return out
