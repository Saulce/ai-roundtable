import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Config


def _fake():
    from types import SimpleNamespace

    class L:
        async def ainvoke(self, p):
            if "下一发言" in p:
                return SimpleNamespace(content=json.dumps({"next_speaker": "杠精", "stalled": False}))
            if "开场立场陈述" in p:
                return SimpleNamespace(content="开场。")
            if "分段摘要" in p:
                return SimpleNamespace(content="## 本段焦点")
            if "整场讨论" in p:
                return SimpleNamespace(content="## 脉络概述\n| 角色 | 开场立场基线 | 结束立场 | 漂移 |")
            return SimpleNamespace(content="发言。")

        async def astream(self, p):
            for t in ["发", "言", "。"]:
                yield SimpleNamespace(content=t)

    return L()


def _stream_events(client, did):
    events = []
    with client.stream("GET", f"/api/discussions/{did}/stream") as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    return events


def test_full_lifecycle(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "e2e.db")
    c = TestClient(create_app(cfg, _fake()))

    did = c.post("/api/discussions", json={
        "topic": "是否应该禁止未成年人使用手机",
        "personas": [{"name": "A", "stance": "支持", "style": "热"},
                     {"name": "B", "stance": "反对", "style": "冷"}],
        "max_turns": 2,
    }).json()["id"]

    assert [e["type"] for e in _stream_events(c, did)][-1] == "paused"

    c.post(f"/api/discussions/{did}/stop")
    rec = c.get(f"/api/discussions/{did}").json()
    assert rec["status"] == "terminated"
    assert any(s["mode"] == "final" for s in rec["summaries"])
    assert len(rec["messages"]) >= 3          # 2 开场 + 至少 1 轮发言
    assert c.get("/api/discussions").json()["discussions"][0]["id"] == did
