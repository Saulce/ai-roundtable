"""节点核心函数（纯逻辑，async）。

决议来源：Wayfinder Map #1 决策票 #3（编排模型）、#6（摘要/总结）。
纯函数：给定 LLM + 输入 → 输出；不依赖 LangGraph。
"""

import json

from app.personas import Persona
from app.prompts import (
    build_opening_prompt,
    build_select_speaker_prompt,
    build_speak_prompt,
    build_summary_prompt,
)


def _strip_code_fence(raw: str) -> str:
    """去掉包裹 JSON 的 markdown 代码围栏（```json ... ```）。"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_speaker_choice(raw: str, names: list[str]) -> tuple[str, bool]:
    """容错解析选发言人 JSON；next_speaker 不在 names 内抛 ValueError。"""
    data = json.loads(_strip_code_fence(raw))
    name = data["next_speaker"]
    if name not in names:
        raise ValueError(f"未知发言人：{name}")
    return name, bool(data["stalled"])


async def generate_opening(llm, topic: str, persona: Persona) -> str:
    """生成一名角色的开场立场陈述。"""
    resp = await llm.ainvoke(build_opening_prompt(topic, persona))
    return resp.content


async def astream_speech(
    llm,
    topic: str,
    persona: Persona,
    opening_statements: list[dict],
    transcript: list[dict],
):
    """流式生成一名角色的自由发言，逐 token yield str。"""
    prompt = build_speak_prompt(topic, persona, opening_statements, transcript)
    async for chunk in llm.astream(prompt):
        yield chunk.content


async def select_next_speaker(
    llm,
    topic: str,
    personas: list[Persona],
    opening_statements: list[dict],
    transcript: list[dict],
) -> tuple[str, bool]:
    """判定下一名发言者，返回 (name, stalled)。"""
    prompt = build_select_speaker_prompt(topic, personas, opening_statements, transcript)
    resp = await llm.ainvoke(prompt)
    return parse_speaker_choice(resp.content, [p.name for p in personas])


async def generate_summary(
    llm,
    topic: str,
    opening_statements: list[dict],
    transcript: list[dict],
    mode: str,
) -> str:
    """按 mode 生成摘要/总结（summary=本段摘要，final=全场总结）。"""
    prompt = build_summary_prompt(topic, opening_statements, transcript, mode)
    resp = await llm.ainvoke(prompt)
    return resp.content
