"""FastAPI REST + SSE 端点。

决议来源：Wayfinder Map #1 决策票 #8（Web 前端与流式交互）。

职责边界：main 只做 HTTP 层（REST + SSE 转发 + 静态挂载），编排交给 sessions，
持久化交给 storage。
"""

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import Config
from app.llm import get_llm
from app.personas import PRESET_PERSONAS, Persona
from app.sessions import SessionManager
from app.storage import Storage


class CreateDiscussionRequest(BaseModel):
    topic: str
    personas: list[Persona]
    max_turns: int | None = None


class _DeferredLLM:
    """延迟构造的真实 LLM：模块导入（如无 API key 的测试环境）不触发 get_llm。

    首次 ainvoke/astream 时才解析；缺 key 的报错延后到真正调用 LLM 时才暴露。
    """

    def __init__(self, config: Config):
        self._config = config
        self._llm = None

    def _resolve(self):
        if self._llm is None:
            self._llm = get_llm(self._config)
        return self._llm

    async def ainvoke(self, prompt):
        return await self._resolve().ainvoke(prompt)

    async def astream(self, prompt):
        async for chunk in self._resolve().astream(prompt):
            yield chunk


def create_app(config: Config, llm=None):
    """组装 FastAPI app；llm=None 时用 get_llm(config)（延迟到首次调用）。"""
    llm = llm if llm is not None else _DeferredLLM(config)
    storage = Storage(config.db_path)
    sessions = SessionManager(llm, storage, default_max_turns=config.default_max_turns)

    app = FastAPI(title="AI 圆桌讨论")

    @app.get("/api/personas")
    async def list_personas():
        return {"personas": [p.model_dump() for p in PRESET_PERSONAS]}

    @app.post("/api/discussions")
    async def create_discussion(req: CreateDiscussionRequest):
        try:
            discussion_id = sessions.create(req.topic, req.personas, req.max_turns)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"id": discussion_id}

    @app.get("/api/discussions/{discussion_id}/stream")
    async def stream(discussion_id: str):
        _require_discussion(storage, discussion_id)

        async def gen():
            try:
                async for event in sessions.run(discussion_id):
                    yield _format_sse(event)
            except Exception as exc:
                # 任何运行期异常（含 LLM 调用失败）都以 error 事件收尾，避免 SSE 中途截断
                yield _format_sse({"type": "error", "detail": str(exc)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/discussions/{discussion_id}/stop")
    async def stop(discussion_id: str):
        _require_discussion(storage, discussion_id)
        result = await sessions.stop(discussion_id)
        return {"status": result["type"]}

    @app.post("/api/discussions/{discussion_id}/continue")
    async def continue_(discussion_id: str):
        _require_discussion(storage, discussion_id)
        sessions.continue_(discussion_id)
        return {"status": "running"}

    @app.get("/api/discussions")
    async def list_discussions():
        return {"discussions": storage.list_discussions()}

    @app.get("/api/discussions/{discussion_id}")
    async def get_discussion(discussion_id: str):
        rec = storage.get_discussion(discussion_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="讨论不存在")
        return rec

    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


def _require_discussion(storage: Storage, discussion_id: str) -> None:
    if storage.get_discussion(discussion_id) is None:
        raise HTTPException(status_code=404, detail="讨论不存在")


def _format_sse(event: dict) -> str:
    """把事件 dict 编码为 SSE 帧：event: <type>\ndata: <json>\n\n。"""
    return (
        f"event: {event.get('type', 'message')}\n"
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    )


app = create_app(Config())
