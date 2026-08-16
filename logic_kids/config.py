"""全局路径配置。

数据目录可用环境变量 LOGIC_KIDS_DATA_DIR 覆盖（测试隔离用），
否则默认使用项目根目录下的 data/。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # 项目根目录
_DATA_OVERRIDE = os.environ.get("LOGIC_KIDS_DATA_DIR")
DATA_DIR = Path(_DATA_OVERRIDE) if _DATA_OVERRIDE else BASE_DIR / "data"
QUESTIONS_DIR = DATA_DIR / "questions"              # 每道题一个 JSON 文件
BANK_INDEX_PATH = DATA_DIR / "bank_index.json"      # 题库索引
IMPORTS_DIR = DATA_DIR / "imports"                  # 外部题待审队列（不入正式题库）
EXTERNAL_DIR = DATA_DIR / "external"                # 外部题库（审核通过后按来源分目录存放）
DB_PATH = DATA_DIR / "profiles.db"                  # 儿童进度 SQLite


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
