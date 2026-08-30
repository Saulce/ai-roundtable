"""讨论 Prompt 模板。

决议来源：Wayfinder Map #1 决策票 #3（讨论编排模型）、#6（摘要与总结）。
"""

from app.personas import Persona

# 每个发言节点可见的最近自由发言条数（可配置常量，测试钉死为 15）。
CONTEXT_WINDOW = 15


def _format_utterances(utterances: list[dict], title: str) -> str:
    """把发言列表格式化为对话正文；空列表给出占位。"""
    if not utterances:
        return f"{title}：\n（暂无）"
    lines = [f"{title}："]
    for u in utterances:
        lines.append(f"- {u['speaker']}：{u['content']}")
    return "\n".join(lines)


def _persona_block(persona: Persona) -> str:
    """角色设定块（名字/立场/风格 + 可选背景）。"""
    lines = [f"名字：{persona.name}", f"立场：{persona.stance}", f"说话风格：{persona.style}"]
    if persona.background:
        lines.append(f"专业背景：{persona.background}")
    return "\n".join(lines)


def build_opening_prompt(topic: str, persona: Persona) -> str:
    """开场陈述轮：让该角色就话题发表初始立场（只表立场、不攻击）。"""
    return (
        "你是一名中文圆桌讨论参与者，请就本次话题发表你的开场陈述。\n"
        f"话题：{topic}\n\n"
        f"{_persona_block(persona)}\n\n"
        "请直接说出你的开场立场陈述：只表明你在这个话题上的立场与核心观点，"
        "不要攻击其他参与者，不要带任何开场白或解释。"
    )


def build_speak_prompt(
    topic: str,
    persona: Persona,
    opening_statements: list[dict],
    recent_transcript: list[dict],
) -> str:
    """自由发言轮：让该角色延续讨论。上下文 = 话题 + 开场陈述（永久在场）+ 最近自由发言。"""
    return (
        "你是一名中文圆桌讨论的参与者，请接着讨论自由发言。\n"
        f"话题：{topic}\n\n"
        f"{_persona_block(persona)}\n\n"
        f"{_format_utterances(opening_statements, '开场陈述')}\n\n"
        f"{_format_utterances(recent_transcript, '最近发言')}\n\n"
        "现在轮到你发言。请延续讨论、保持你的立场与说话风格，直接说出你的发言内容，"
        "不要任何解说、引用或结束语。"
    )


def build_select_speaker_prompt(
    topic: str,
    personas: list[Persona],
    opening_statements: list[dict],
    recent_transcript: list[dict],
) -> str:
    """选发言人轮：决定下一位自由发言的角色。讨论自由、可连续选同一人；卡住时指定沉默最久者。"""
    names = "\n".join(f"{i}. {p.name}" for i, p in enumerate(personas, 1))
    return (
        "你是中文圆桌讨论的调度者，请决定下一位自由发言的角色。\n"
        f"话题：{topic}\n"
        f"参与者：\n{names}\n\n"
        f"{_format_utterances(opening_statements, '开场陈述')}\n\n"
        f"{_format_utterances(recent_transcript, '最近发言')}\n\n"
        "规则：\n"
        "- 讨论是自由发言，可以连续多次选择同一人（他想发几句就发几句）。\n"
        "- 如果讨论卡住（很长时间无人发言），请选择参与最少、沉默最久的角色来推进，并把 stalled 设为 true。\n"
        "- 否则选择最适合继续话题的人，并把 stalled 设为 false。\n\n"
        "只输出 JSON，不要输出任何其他内容，格式："
        '{"next_speaker": "角色名", "stalled": true 或 false}'
    )


def build_summary_prompt(
    topic: str,
    opening_statements: list[dict],
    transcript: list[dict],
    mode: str,
) -> str:
    """总结/摘要 prompt：mode="summary"（暂停·轻）或 mode="final"（终止·全）。均不下结论。"""
    if mode == "summary":
        return (
            "你是一名中文圆桌讨论的摘要记录员，请为「本段」讨论写一份轻量摘要。\n"
            f"话题：{topic}\n\n"
            f"{_format_utterances(opening_statements, '开场陈述')}\n\n"
            f"{_format_utterances(transcript, '本段发言')}\n\n"
            "请输出结构化 Markdown 摘要，包含以下小节：\n"
            "## 本段焦点\n"
            "## 各方本段要点\n"
            "## 本段分歧点\n"
            "## 立场变动提示\n\n"
            "只陈述讨论中的事实，不下任何结论。"
        )
    if mode == "final":
        return (
            "你是一名中文圆桌讨论的总结记录员，请为整场讨论写一份完整总结。\n"
            f"话题：{topic}\n\n"
            f"{_format_utterances(opening_statements, '开场陈述')}\n\n"
            f"{_format_utterances(transcript, '全场发言')}\n\n"
            "请输出结构化 Markdown 总结，包含以下小节：\n"
            "## 讨论脉络\n"
            "## 各方核心观点\n"
            "## 核心分歧点\n"
            "## 未决问题\n"
            "## 开场 vs 结束立场对比\n\n"
            "其中「开场 vs 结束立场对比」必须为 Markdown 表格，列为：\n"
            "| 角色 | 开场立场基线 | 结束立场 | 漂移 |\n\n"
            "只陈述讨论中的事实，不下任何结论。"
        )
    raise ValueError(f"未知的总结模式：{mode}")
