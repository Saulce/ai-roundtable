from app.personas import PRESET_PERSONAS
from app.prompts import (
    build_opening_prompt,
    build_speak_prompt,
    build_select_speaker_prompt,
    build_summary_prompt,
    CONTEXT_WINDOW,
)


def test_context_window_is_15():
    assert CONTEXT_WINDOW == 15


def test_opening_prompt_includes_topic_and_persona_fields():
    p = PRESET_PERSONAS[0]
    s = build_opening_prompt("是否应该禁止未成年人使用手机", p)
    assert "是否应该禁止未成年人使用手机" in s
    assert p.name in s and p.stance in s and p.style in s


def test_speak_prompt_contains_recent_transcript():
    p = PRESET_PERSONAS[1]
    recent = [{"speaker": "好为人师者", "content": "我认为应该禁止。", "kind": "speech"}]
    s = build_speak_prompt("话题", p, [], recent)
    assert "我认为应该禁止。" in s


def test_select_prompt_lists_all_persona_names():
    s = build_select_speaker_prompt("话题", PRESET_PERSONAS[:3], [], [])
    for name in ["好为人师者", "杠精", "中立质疑者"]:
        assert name in s


def test_summary_prompt_mode_final_has_comparison_table():
    s = build_summary_prompt("话题", [], [], mode="final")
    assert "对比" in s and "漂移" in s and "|" in s


def test_summary_prompt_mode_summary_lighter():
    s = build_summary_prompt("话题", [], [], mode="summary")
    assert "本段焦点" in s and "未决问题" not in s
