from app.config import Config
from app.llm import get_llm


def test_config_defaults(monkeypatch):
    for key in ["ROUNDTABLE_BASE_URL", "ROUNDTABLE_API_KEY", "ROUNDTABLE_MODEL",
                "ROUNDTABLE_DB_PATH", "ROUNDTABLE_DEFAULT_MAX_TURNS"]:
        monkeypatch.delenv(key, raising=False)
    cfg = Config()
    assert cfg.base_url == "https://api.deepseek.com/v1"
    assert cfg.model == "deepseek-chat"
    assert cfg.db_path == "roundtable.db"
    assert cfg.default_max_turns == 15


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("ROUNDTABLE_API_KEY", "sk-test")
    monkeypatch.setenv("ROUNDTABLE_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ROUNDTABLE_DEFAULT_MAX_TURNS", "8")
    cfg = Config()
    assert cfg.api_key == "sk-test"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.default_max_turns == 8


def test_get_llm_uses_config():
    cfg = Config()
    cfg.base_url = "http://localhost:8000/v1"
    cfg.api_key = "EMPTY"
    cfg.model = "test-model"
    llm = get_llm(cfg)
    assert llm.model_name == "test-model"
