"""LogiQA2.0 导入适配器（专家意见 Phase 3 评估候选源）。

许可证：CC BY-NC-SA 4.0 —— 仅限研究/非商业用途，导入时在 source_info.license
中明确记录，并由导入报告提示。若项目未来商业化，应改用 Apache-2.0 的 BIG-bench。

LogiQA 是自然语言阅读理解/逻辑推理选择题，**不强行转换成 DSL**
（专家意见第九节）：只做结构归一化，标记 logic_validated=False，
进入待审队列等待人工/LLM 改写与验证，绝不过闸直接进正式题库。
"""
from __future__ import annotations

import json
import urllib.request

from ..normalizer import NormalizedQuestion
from ..provenance import make_source, make_provenance

SOURCE_NAME = "LogiQA2.0"
LICENSE = "CC-BY-NC-SA-4.0"

_BASE_URL = ("https://raw.githubusercontent.com/csitfun/logiqa2.0/main/"
             "logiqa/DATA/LOGIQA/{split}")
_CDN_URL = ("https://cdn.jsdelivr.net/gh/csitfun/logiqa2.0@main/"
            "logiqa/DATA/LOGIQA/{split}")


def fetch(task: str = "dev", limit: int = None, lang: str = "zh") -> list:
    """拉取 LogiQA 原始 JSONL（每行一道题）。

    lang="zh" 用 *_zh.txt（官方中文版），lang="en" 用英文原版。
    """
    fname = f"{task}_zh.txt" if lang == "zh" else f"{task}.txt"
    urls = [_CDN_URL.format(split=fname), _BASE_URL.format(split=fname)]
    last_err = None
    for url in urls:
        for _ in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    lines = r.read().decode("utf-8").splitlines()
                break
            except Exception as e:  # 网络抖动：换镜像/重试
                last_err = e
        else:
            continue
        break
    else:
        raise RuntimeError(f"LogiQA 下载失败：{last_err}") from last_err
    items = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            obj["_split"] = task
            obj["_lang"] = lang
            items.append(obj)
        except json.JSONDecodeError:
            continue
    return items[:limit] if limit is not None else items


def normalize(item: dict) -> NormalizedQuestion | None:
    """LogiQA 原始行 -> 统一题目（结构校验；无 DSL，等待人工改写）。"""
    if not isinstance(item, dict):
        return None
    text = (item.get("text") or "").strip()
    question = (item.get("question") or "").strip()
    options = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
    answer = item.get("answer")
    oid = str(item.get("id") or item.get("example_id") or "")
    if not text or not question or len(options) < 2:
        return None
    if not isinstance(answer, int) or not (0 <= answer < len(options)):
        return None

    source = make_source(name=SOURCE_NAME, license=LICENSE,
                         dataset_id=(f"split={item.get('_split', '')}"
                                     f",lang={item.get('_lang', 'zh')}"),
                         original_id=oid,
                         url=_BASE_URL.format(
                             split=item.get("_split", "dev")
                             + ("_zh" if item.get("_lang") == "zh" else "")
                             + ".txt"))
    prov = make_provenance(translator="", modified=False)
    return NormalizedQuestion(
        source=source,
        provenance=prov,
        qtype="external_text",
        story_title=f"LogiQA · #{oid}",
        story_text=text,
        question_prompt=question,
        options=options,
        answer=answer,
        explanation="LogiQA 原始题（CC BY-NC-SA 4.0，非商业），未经改写与逻辑验证。",
    )
