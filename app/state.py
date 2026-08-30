"""讨论运行状态（DiscussionState）。

决议来源：Wayfinder Map #1 决策票 #3（讨论编排模型）、#4（结束模型）、#6（摘要与总结）。
"""

from typing import Literal, TypedDict


class Utterance(TypedDict):
    """一条发言记录。

    - kind="opening" 表示开场陈述（仅开场轮，永久在场）
    - kind="speech" 表示自由发言（按序追加进 transcript）
    """

    speaker: str
    content: str
    kind: Literal["opening", "speech"]


class DiscussionState(TypedDict, total=False):
    """一次讨论（或一个讨论段）的运行状态。

    约定：
    - opening_statements 仅开场陈述、永久在场；transcript 仅自由发言、按序追加。
    - max_turns 为本段累计轮次预算（<=0 表示仅手动停止）；segment_start 记录本段起始 turn_count，
      用于切出「本段」转录生成轻量摘要。
    - status: running | paused | terminated；mode: summary（暂停·轻摘要）| final（终止·全场总结）。
    """

    topic: str
    personas: list[dict]
    opening_statements: list[Utterance]
    transcript: list[Utterance]
    next_speaker: str
    stalled: bool
    turn_count: int
    max_turns: int
    segment_start: int
    status: Literal["running", "paused", "terminated"]
    mode: Literal["summary", "final"]
    summary: str
