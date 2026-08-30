import asyncio
import json
import pytest

from app.personas import PRESET_PERSONAS
from app.nodes import (
    generate_opening,
    astream_speech,
    select_next_speaker,
    parse_speaker_choice,
    generate_summary,
)


def test_generate_opening_calls_llm_and_returns_text(fake_llm):
    llm = fake_llm(lambda prompt: "我支持这个主张，理由如下。")
    out = asyncio.run(generate_opening(llm, "话题", PRESET_PERSONAS[0]))
    assert out == "我支持这个主张，理由如下。"
    assert len(llm.invoke_calls) == 1
    assert "话题" in llm.invoke_calls[0]


def test_astream_speech_streams_tokens(fake_llm):
    llm = fake_llm(lambda prompt: ["我", "不", "同", "意", "。"])
    tokens = asyncio.run(_collect_tokens(llm))
    assert tokens == ["我", "不", "同", "意", "。"]


async def _collect_tokens(llm):
    return [t async for t in astream_speech(llm, "话题", PRESET_PERSONAS[1], [], [])]


def test_parse_speaker_choice_extracts_name_and_stalled():
    names = ["好为人师者", "杠精", "中立质疑者"]
    name, stalled = parse_speaker_choice('{"next_speaker": "杠精", "stalled": true}', names)
    assert name == "杠精"
    assert stalled is True


def test_parse_speaker_choice_tolerates_markdown_fence():
    names = ["好为人师者", "杠精", "中立质疑者"]
    raw = '```json\n{"next_speaker": "好为人师者", "stalled": false}\n```'
    name, stalled = parse_speaker_choice(raw, names)
    assert name == "好为人师者"
    assert stalled is False


def test_parse_speaker_choice_rejects_unknown_name():
    with pytest.raises(ValueError):
        parse_speaker_choice('{"next_speaker": "不存在", "stalled": false}', ["好为人师者"])


def test_select_next_speaker_roundtrips(fake_llm):
    llm = fake_llm(lambda prompt: json.dumps({"next_speaker": "中立质疑者", "stalled": True}))
    name, stalled = asyncio.run(
        select_next_speaker(llm, "话题", PRESET_PERSONAS[:3], [], [])
    )
    assert (name, stalled) == ("中立质疑者", True)


def test_generate_summary_uses_mode(fake_llm):
    llm = fake_llm(lambda prompt: "## 本段焦点\n..." if "本段焦点" in prompt else "## 脉络概述\n...")
    assert asyncio.run(generate_summary(llm, "话题", [], [], "summary")).startswith("## 本段焦点")
    assert asyncio.run(generate_summary(llm, "话题", [], [], "final")).startswith("## 脉络概述")
