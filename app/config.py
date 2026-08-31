import os
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录的 .env（README 快速开始中 cp .env.example .env 的产物）。
# 默认 override=False：已导出的环境变量优先于 .env，避免覆盖 shell 里的显式配置。
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Config:
    """从环境变量读取配置，变量名见各字段（ROUNDTABLE_*）。"""

    def __init__(self):
        self.base_url = os.getenv("ROUNDTABLE_BASE_URL", "https://api.deepseek.com/v1")
        self.api_key = os.getenv("ROUNDTABLE_API_KEY", "")
        self.model = os.getenv("ROUNDTABLE_MODEL", "deepseek-chat")
        self.db_path = os.getenv("ROUNDTABLE_DB_PATH", "roundtable.db")
        self.default_max_turns = int(os.getenv("ROUNDTABLE_DEFAULT_MAX_TURNS", "15"))
