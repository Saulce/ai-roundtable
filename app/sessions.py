"""运行中讨论的生命周期编排（SessionManager）。

决议来源：Wayfinder Map #1 决策票 #3（编排）、#4（结束模型）、#6（摘要/总结）；
spec：Task 7（GitHub issue #15）。

职责：把 Task 5 的 LangGraph 图 + Task 6 的 SQLite 存储焊成「可跑一次讨论」的编排层：
- create() 建讨论（写 storage）
- run() 跑一个段（async generator 产出 SSE 事件：opening/token/message/paused）
- stop() 手动停止 → 终止 + 全场总结（mode=final）
- continue_() 标记暂停后可续跑

关键约定：
- max_turns = 每段 N 轮；图内 max_turns = 本段累计预算（turn_count + N）；
  _per_segment 保存原始 N。
- 继续时开场已存在 → 图内跳过开场轮，不重复开场。
- SQLite 为转录单一事实源：段结束时从 storage 重建累计状态。
"""

import asyncio
import contextlib
import uuid
from typing import Any, AsyncIterator

from app.graph import build_graph
from app.nodes import generate_summary
from app.personas import Persona, validate_personas
from app.storage import Storage


class SessionManager:
    """一次讨论（或分段继续）的生命周期编排。

    事件类型（与 Task 5 图一致 + terminated）：
    - {"type": "opening", "speaker", "content"}  开场陈述
    - {"type": "token", "speaker", "content"}    逐 token
    - {"type": "message", "speaker", "content"}  一条完整自由发言
    - {"type": "paused", "summary", "turns"}     达轮次上限 → 暂停
    - {"type": "terminated", "summary"}          手动停止 → 终止
    """

    def __init__(self, llm, storage: Storage, default_max_turns: int = 15):
        self.llm = llm
        self.storage = storage
        self.default_max_turns = default_max_turns
        # 每段原始轮次预算 N（图内 max_turns = 累计 turn_count + N）
        self._per_segment: dict[str, int] = {}
        # 正在进行中的段任务（discussion_id → task），供 stop() 取消 / 双跑防抖
        self._running_tasks: dict[str, asyncio.Task] = {}
        # 已调用 continue_ 待消费的讨论（discussion_id → True），段开始即清除
        self._continue_flags: dict[str, bool] = {}

    # ---- 生命周期 ----

    def create(self, topic: str, personas: list[Persona], max_turns: int | None = None) -> str:
        """建讨论并写 storage；max_turns=None → 默认每段 N。返回 discussion_id。"""
        validate_personas(personas)
        n = self.default_max_turns if max_turns is None else max_turns
        discussion_id = uuid.uuid4().hex
        self.storage.create_discussion(
            discussion_id,
            topic,
            [p.model_dump() for p in personas],
            n,
        )
        self._per_segment[discussion_id] = n
        return discussion_id

    def continue_(self, discussion_id: str) -> bool:
        """标记暂停后可续跑：要求处于 paused，恢复原始每段 N，供下一次 run 消费。"""
        disc = self._load_discussion(discussion_id)
        if disc["status"] != "paused":
            raise ValueError(f"仅暂停的讨论可继续，当前状态：{disc['status']}")
        self._per_segment[discussion_id] = disc["max_turns"]
        self._continue_flags[discussion_id] = True
        return True

    async def run(self, discussion_id: str) -> AsyncIterator[dict[str, Any]]:
        """跑一个段：从 storage 重建累计状态，转发图事件并逐事件持久化。"""
        disc = self._load_discussion(discussion_id)
        if disc["status"] == "terminated":
            raise ValueError("已终止的讨论不能继续")
        if discussion_id in self._running_tasks:
            raise RuntimeError(f"讨论正在运行中：{discussion_id}")
        if disc["status"] == "paused" and not self._continue_flags.get(discussion_id):
            raise ValueError(f"讨论已暂停，请先调用 continue_：{discussion_id}")
        self._continue_flags.pop(discussion_id, None)

        self.storage.update_status(discussion_id, "running")
        graph = build_graph(self.llm)
        state = self._rebuild_state(discussion_id, disc)
        self._running_tasks[discussion_id] = asyncio.current_task()
        try:
            async for ev in graph.astream(state, stream_mode="custom"):
                yield self._persist_event(discussion_id, ev)
        finally:
            self._running_tasks.pop(discussion_id, None)

    async def stop(self, discussion_id: str) -> dict[str, Any]:
        """手动停止 → 终止：取消进行中的段，触发全场总结（mode=final）。"""
        task = self._running_tasks.pop(discussion_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        summary = await self._final_summary(discussion_id)
        self.storage.save_summary(discussion_id, "final", summary)
        self.storage.update_status(discussion_id, "terminated")
        return {"type": "terminated", "summary": summary}

    # ---- 内部 ----

    def _load_discussion(self, discussion_id: str) -> dict:
        """读 storage；讨论不存在统一抛 KeyError。"""
        disc = self.storage.get_discussion(discussion_id)
        if disc is None:
            raise KeyError(f"讨论不存在：{discussion_id}")
        return disc

    @staticmethod
    def _split_messages(disc: dict) -> tuple[list[dict], list[dict]]:
        """按 kind 把 storage 消息拆成 (开场陈述, 自由发言)，顺序保持不变。"""
        opening = [
            {"speaker": m["speaker"], "content": m["content"], "kind": "opening"}
            for m in disc["messages"]
            if m["kind"] == "opening"
        ]
        transcript = [
            {"speaker": m["speaker"], "content": m["content"], "kind": "message"}
            for m in disc["messages"]
            if m["kind"] == "message"
        ]
        return opening, transcript

    def _rebuild_state(self, discussion_id: str, disc: dict) -> dict[str, Any]:
        """从 storage 重建图输入：开场永久在场，自由发言累计，图内 max_turns = turn_count + N。"""
        opening, transcript = self._split_messages(disc)
        turn_count = len(transcript)
        n = self._per_segment.get(discussion_id, disc["max_turns"])
        # 图内 max_turns = 本段累计预算 = turn_count + N；N<=0 表示仅手动停止（图内永不按轮次暂停）
        budget = 0 if n <= 0 else turn_count + n
        return {
            "topic": disc["topic"],
            "personas": disc["personas"],
            "opening_statements": opening,
            "transcript": transcript,
            "next_speaker": "",
            "stalled": False,
            "turn_count": turn_count,
            "max_turns": budget,
            "segment_start": turn_count,
            "status": "running",
            "mode": "",
            "summary": "",
        }

    def _persist_event(self, discussion_id: str, ev: dict[str, Any]) -> dict[str, Any]:
        """逐事件持久化：opening/message 落转录，paused 落摘要 + 状态；token 不落库。"""
        etype = ev["type"]
        if etype == "opening":
            self.storage.append_message(
                discussion_id,
                {"kind": "opening", "speaker": ev["speaker"], "content": ev["content"]},
            )
        elif etype == "message":
            self.storage.append_message(
                discussion_id,
                {"kind": "message", "speaker": ev["speaker"], "content": ev["content"]},
            )
        elif etype == "paused":
            self.storage.save_summary(discussion_id, "summary", ev["summary"])
            self.storage.update_status(discussion_id, "paused")
        return ev

    async def _final_summary(self, discussion_id: str) -> str:
        """全场总结：读 storage 重建开场 + 全场转录，走 nodes.generate_summary(mode="final")。"""
        disc = self._load_discussion(discussion_id)
        opening, transcript = self._split_messages(disc)
        return await generate_summary(
            self.llm,
            disc["topic"],
            opening,
            transcript,
            mode="final",
        )

    def _run_sync(self, discussion_id: str) -> list[dict[str, Any]]:
        """测试/脚本辅助：同步跑完一个段并收集全部事件。"""

        async def _collect() -> list[dict[str, Any]]:
            events = []
            async for ev in self.run(discussion_id):
                events.append(ev)
            return events

        return asyncio.run(_collect())
