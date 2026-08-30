import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Config


def _fake_llm():
    from types import SimpleNamespace

    class LLM:
        async def ainvoke(self, prompt):
            if "下一发言" in prompt:
                return SimpleNamespace(content=json.dumps({"next_speaker": "杠精", "stalled": False}))
            if "开场立场陈述" in prompt:
                return SimpleNamespace(content="开场。")
            if "分段摘要" in prompt:
                return SimpleNamespace(content="## 本段焦点")
            if "整场讨论" in prompt:
                return SimpleNamespace(content="## 脉络概述")
            return SimpleNamespace(content="发言。")

        async def astream(self, prompt):
            for tok in ["发", "言", "。"]:
                yield SimpleNamespace(content=tok)

    return LLM()


def _client(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "api.db")
    app = create_app(cfg, _fake_llm())
    return TestClient(app)


def test_list_personas(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/personas")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()["personas"]]
    assert names[:3] == ["好为人师者", "杠精", "中立质疑者"]


def test_create_and_stream(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/discussions", json={
        "topic": "是否应该禁止未成年人使用手机",
        "personas": [{"name": "A", "stance": "支持", "style": "激进"},
                     {"name": "B", "stance": "反对", "style": "冷静"}],
        "max_turns": 2,
    })
    assert r.status_code == 200
    did = r.json()["id"]

    events = []
    with c.stream("GET", f"/api/discussions/{did}/stream") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    types = [e["type"] for e in events]
    assert "opening" in types
    assert types[-1] == "paused"


def test_stop_after_stream(tmp_path):
    c = _client(tmp_path)
    did = c.post("/api/discussions", json={
        "topic": "t", "personas": [{"name": "A", "stance": "x", "style": "y"},
                                   {"name": "B", "stance": "z", "style": "w"}],
        "max_turns": None,
    }).json()["id"]
    c.get(f"/api/discussions/{did}/stream")  # 消费完整流（自动暂停）
    r = c.post(f"/api/discussions/{did}/stop")
    assert r.json()["status"] == "terminated"
    assert c.get(f"/api/discussions/{did}").json()["status"] == "terminated"


def test_validation_rejects_one_persona(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/discussions", json={
        "topic": "t", "personas": [{"name": "A", "stance": "x", "style": "y"}], "max_turns": None,
    })
    assert r.status_code == 422
