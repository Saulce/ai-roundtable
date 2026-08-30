"""讨论图组装：单循环图 + 轮次上限路由。

决议来源：Wayfinder Map #1 决策票 #3（编排模型）、#4（结束模型）。

本模块自包含：节点逻辑与 prompt 内联于此（Task 4 的 nodes.py/prompts.py
合并后可改为焊接 nodes.py 的纯函数）。事件经 `get_stream_writer` 以
`stream_mode="custom"` 输出，供 Task 7/8（SessionManager / SSE）转发。

事件约定：
- {"type": "opening", "speaker": str, "content": str}  开场陈述轮
- {"type": "token",   "speaker": str, "content": str}  逐 token 流式
- {"type": "message", "speaker": str, "content": str}  一条完整发言
- {"type": "paused",  "summary": str, "turns": int}    达轮次上限 → 暂停 → 分段摘要
"""

import json
from typing import Any, TypedDict

try:
    from langgraph.config import get_stream_writer
except ImportError:  # langgraph < 1.0 时代曾位于 langgraph.types
    from langgraph.types import get_stream_writer  # type: ignore[no-redef]
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class DiscussionState(TypedDict, total=False):
    """讨论运行状态（与 tests/conftest 的 _base_state 对齐）。"""

    topic: str
    personas: list[dict[str, Any]]
    opening_statements: list[dict[str, Any]]
    transcript: list[dict[str, Any]]
    next_speaker: str
    stalled: bool
    turn_count: int
    max_turns: int
    segment_start: int
    status: str
    mode: str
    summary: str


def should_end(state: DiscussionState) -> str:
    """轮次上限路由。

    max_turns > 0 且 turn_count >= max_turns → "summarize"（暂停 → 分段摘要）；
    否则 → "select_speaker"（继续选人发言）。max_turns <= 0 永不因轮次暂停。
    """
    max_turns = state.get("max_turns", 0)
    turn_count = state.get("turn_count", 0)
    if max_turns > 0 and turn_count >= max_turns:
        return "summarize"
    return "select_speaker"


def _opening_prompt(state: DiscussionState, persona: dict[str, Any]) -> str:
    return (
        f"你是「{persona['name']}」，正在参加一场关于「{state['topic']}」的圆桌讨论。\n"
        f"你的立场：{persona['stance']}。你的说话风格：{persona['style']}。\n"
        "请以你的身份做开场立场陈述，用一段话表明你对本话题的立场。只表明立场，不要攻击或反驳他人。"
    )


def _select_speaker_prompt(state: DiscussionState) -> str:
    names = "、".join(p["name"] for p in state["personas"])
    return (
        f"你是圆桌讨论的控场者。当前讨论话题：「{state['topic']}」。你不发言，只判定下一发言的人。\n"
        f"可选发言人（只能从中选一个）：{names}。\n"
        f"最近讨论内容：{_fmt_utterances(state.get('transcript', []))}\n"
        "请只输出 JSON，不要任何其他文字："
        '{"next_speaker": "<角色名>", "stalled": true 或 false}'
    )


def _speak_prompt(state: DiscussionState, speaker: str) -> str:
    return (
        f"你是「{speaker}」，正在参加一场关于「{state['topic']}」的圆桌讨论。\n"
        f"最近讨论内容：{_fmt_utterances(state.get('transcript', []))}\n"
        "请发言一次：自然地表达你的观点，可以回应最近的发言，也可以补充新论据。"
        "直接输出你的发言内容，不要复述场景。"
    )


def _summary_prompt(state: DiscussionState) -> str:
    return (
        f"请为本段圆桌讨论写一份轻量摘要。\n"
        f"讨论话题：{state['topic']}\n"
        f"开场陈述：{_fmt_utterances(state.get('opening_statements', []))}\n"
        f"本段讨论记录：{_fmt_utterances(state.get('transcript', []))}\n"
        "请按以下 Markdown 结构输出：\n"
        "## 本段焦点\n## 各方本段要点\n## 本段分歧点\n## 轻量立场变动提示"
    )


def _fmt_utterances(utterances: list[dict[str, Any]]) -> str:
    if not utterances:
        return "（暂无）"
    return "\n".join(
        f"{u.get('speaker', '?')}：{u.get('content', '')}" for u in utterances
    )


def build_graph(llm) -> CompiledStateGraph:
    """组装单循环讨论图：opening → select_speaker → speak → (should_end) → summarize | select_speaker。"""

    async def opening(state: DiscussionState) -> dict[str, Any]:
        writer = get_stream_writer()
        if state.get("opening_statements"):
            # 已开场 → 跳过开场陈述轮，不输出任何事件
            return {}
        statements = []
        for persona in state["personas"]:
            resp = await llm.ainvoke(_opening_prompt(state, persona))
            content = resp.content
            statements.append(
                {"speaker": persona["name"], "content": content, "kind": "opening"}
            )
            writer({"type": "opening", "speaker": persona["name"], "content": content})
        return {"opening_statements": statements}

    async def select_speaker(state: DiscussionState) -> dict[str, Any]:
        resp = await llm.ainvoke(_select_speaker_prompt(state))
        data = json.loads(resp.content)
        return {
            "next_speaker": data["next_speaker"],
            "stalled": bool(data.get("stalled", False)),
        }

    async def speak(state: DiscussionState) -> dict[str, Any]:
        writer = get_stream_writer()
        speaker = state["next_speaker"]
        tokens = []
        async for chunk in llm.astream(_speak_prompt(state, speaker)):
            token = chunk.content
            tokens.append(token)
            writer({"type": "token", "speaker": speaker, "content": token})
        content = "".join(tokens)
        writer({"type": "message", "speaker": speaker, "content": content})
        transcript = list(state.get("transcript") or [])
        transcript.append(
            {"speaker": speaker, "content": content, "kind": "message"}
        )
        return {
            "transcript": transcript,
            "turn_count": state.get("turn_count", 0) + 1,
        }

    async def summarize(state: DiscussionState) -> dict[str, Any]:
        writer = get_stream_writer()
        resp = await llm.ainvoke(_summary_prompt(state))
        summary = resp.content
        writer(
            {
                "type": "paused",
                "summary": summary,
                "turns": state.get("turn_count", 0),
            }
        )
        return {"status": "paused", "summary": summary}

    builder = StateGraph(DiscussionState)
    builder.add_node("opening", opening)
    builder.add_node("select_speaker", select_speaker)
    builder.add_node("speak", speak)
    builder.add_node("summarize", summarize)
    builder.add_edge(START, "opening")
    builder.add_edge("opening", "select_speaker")
    builder.add_edge("select_speaker", "speak")
    builder.add_conditional_edges(
        "speak",
        should_end,
        {
            "select_speaker": "select_speaker",
            "summarize": "summarize",
        },
    )
    builder.add_edge("summarize", END)
    return builder.compile()
