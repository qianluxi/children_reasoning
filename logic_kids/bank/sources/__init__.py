"""外部题库源注册表（专家意见第十八节：Level B 开放题库）。"""
from __future__ import annotations

from . import bigbench, logiqa

SOURCES = {
    "bigbench": bigbench,
    "logiqa": logiqa,
}

SOURCE_INFO = {
    name: {"license": mod.LICENSE, "name": mod.SOURCE_NAME}
    for name, mod in SOURCES.items()
}


def get(name: str):
    if name not in SOURCES:
        raise KeyError(f"未知题库源：{name}（可选：{', '.join(SOURCES)}）")
    return SOURCES[name]
