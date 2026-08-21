import os


class Config:
    """从环境变量读取配置，变量名见各字段（ROUNDTABLE_*）。"""

    def __init__(self):
        self.base_url = os.getenv("ROUNDTABLE_BASE_URL", "https://api.deepseek.com/v1")
        self.api_key = os.getenv("ROUNDTABLE_API_KEY", "")
        self.model = os.getenv("ROUNDTABLE_MODEL", "deepseek-chat")
        self.db_path = os.getenv("ROUNDTABLE_DB_PATH", "roundtable.db")
        self.default_max_turns = int(os.getenv("ROUNDTABLE_DEFAULT_MAX_TURNS", "15"))
