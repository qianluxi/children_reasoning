"""全局路径配置。"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # 项目根目录
DATA_DIR = BASE_DIR / "data"
QUESTIONS_DIR = DATA_DIR / "questions"              # 每道题一个 JSON 文件
BANK_INDEX_PATH = DATA_DIR / "bank_index.json"      # 题库索引
DB_PATH = DATA_DIR / "profiles.db"                  # 儿童进度 SQLite


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
