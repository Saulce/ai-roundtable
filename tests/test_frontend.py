"""Task 9 前端冒烟测试。

来源：GitHub issue #17 spec。静态 HTML/CSS/JS 无构建步骤，pytest 只钉死：
- 发起页文案「发起讨论」（测试钉死）
- 讨论页三栏结构 + 顶栏控件（防止实现删栏/改文案回归）
- 静态资源经 create_app 挂载到 /
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Config


def _noop_llm():
    from types import SimpleNamespace

    class L:
        async def ainvoke(self, p):
            return SimpleNamespace(content="x")

        async def astream(self, p):
            yield SimpleNamespace(content="x")

    return L()


def _client(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "f.db")
    app = create_app(cfg, llm=_noop_llm())
    return TestClient(app)


def test_frontend_served(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "发起讨论" in r.text


def test_discussion_view_markup(tmp_path):
    """讨论页三栏结构 + 顶栏控件钉死，防回归删栏。"""
    c = _client(tmp_path)
    r = c.get("/")
    for token in ["重新发起", "■ 叫停", "话题 · 角色", "时间线", "立场漂移 · 摘要"]:
        assert token in r.text, f"讨论页缺少元素：{token}"


def test_frontend_assets_served(tmp_path):
    c = _client(tmp_path)
    for path in ["/style.css", "/app.js"]:
        r = c.get(path)
        assert r.status_code == 200, f"静态资源未挂载：{path}"
