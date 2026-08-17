"""图形化渲染：把纯文本的图形题按需转成真正的图片（迷宫/ARC 格子/长方形计数）。

Web 通过 /api/question/<qid>/visual 取图；没有图形内容的题返回 None。
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# ARC 1D 色板（0=黑，1~9 彩）
_ARC_COLORS = {
    0: "#111111", 1: "#0074D9", 2: "#FF4136", 3: "#2ECC40", 4: "#FFDC00",
    5: "#AAAAAA", 6: "#F012BE", 7: "#FF851B", 8: "#7FDBFF", 9: "#B10DC9",
}


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_maze(question) -> bytes | None:
    md = question.metadata or {}
    grid = md.get("grid")
    if not grid:
        return None
    rows = [list(str(r)) for r in grid]
    h, w = len(rows), max(len(r) for r in rows)
    cell, pad = 30, 14
    img = Image.new("RGB", (w * cell + pad * 2, h * cell + pad * 2), "#FFFFFF")
    d = ImageDraw.Draw(img)
    start, goal, wall = (str(md.get(k, "")) for k in ("start", "goal", "wall"))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            x0, y0 = pad + x * cell, pad + y * cell
            if ch == wall:
                d.rectangle([x0, y0, x0 + cell, y0 + cell], fill="#5A5A66")
            else:
                d.rectangle([x0, y0, x0 + cell, y0 + cell],
                            fill="#FBF6EA", outline="#DDD5C5")
            if ch == start:
                d.ellipse([x0 + 5, y0 + 5, x0 + cell - 5, y0 + cell - 5],
                          fill="#27AE60")
                d.text((x0 + cell // 2 - 5, y0 + cell // 2 - 9), "S",
                       fill="white", font=_font(15))
            elif ch == goal:
                d.ellipse([x0 + 5, y0 + 5, x0 + cell - 5, y0 + cell - 5],
                          fill="#E74C3C")
                d.text((x0 + cell // 2 - 5, y0 + cell // 2 - 9), "G",
                       fill="white", font=_font(15))
    return _png(img)


def _row_image(row, cell: int) -> Image.Image:
    n = len(row)
    img = Image.new("RGB", (n * cell, cell), "#FFFFFF")
    d = ImageDraw.Draw(img)
    for i, v in enumerate(row):
        color = _ARC_COLORS.get(int(v), "#888888")
        d.rectangle([i * cell, 0, i * cell + cell, cell], fill=color)
    return img


def render_arc(question) -> bytes | None:
    md = question.metadata or {}
    train = md.get("train_examples") or []
    test = md.get("test_example") or {}
    if not train:
        return None
    cell, gap, pad = 22, 18, 16
    shown = train[:3]
    test_in = test.get("input") or []

    def width(row):
        return len(row) * cell

    max_w = max([width(e["input"]) + width(e["output"]) + 40
                 for e in shown] + [width(test_in)])
    img_h = pad * 2 + len(shown) * cell + len(shown) * gap + (cell + 30) + gap
    img = Image.new("RGB", (max_w + pad * 2, img_h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    y = pad
    f = _font(13)
    for i, ex in enumerate(shown):
        d.text((pad, y - 4), f"例子 {i + 1}", fill="#333333", font=f)
        inp = _row_image(ex["input"], cell)
        out = _row_image(ex["output"], cell)
        img.paste(inp, (pad, y))
        d.text((pad + len(ex["input"]) * cell + 8, y + cell // 2 - 7), "→",
               fill="#888888", font=f)
        img.paste(out, (pad + len(ex["input"]) * cell + 30, y))
        y += cell + gap
    d.text((pad, y - 4), "测试输入", fill="#E74C3C", font=f)
    img.paste(_row_image(test_in, cell), (pad, y))
    return _png(img)


def render_rect(question) -> bytes | None:
    md = question.metadata or {}
    puzzle = md.get("puzzle")
    if isinstance(puzzle, str):
        lines = puzzle.splitlines()
    elif isinstance(puzzle, list):
        lines = [str(x) for x in puzzle]
    else:
        return None
    if not lines:
        return None
    cell, pad = 22, 16
    rows = [list(str(r)) for r in lines]
    h, w = len(rows), max(len(r) for r in rows)
    img = Image.new("RGB", (w * cell + pad * 2, h * cell + pad * 2), "#FFFFFF")
    d = ImageDraw.Draw(img)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            x0, y0 = pad + x * cell, pad + y * cell
            dark = ch in ("#", "█", "@", "X")
            d.rectangle([x0, y0, x0 + cell, y0 + cell],
                        fill="#3B3B4A" if dark else "#F5F2EB",
                        outline="#DDD5C5")
    return _png(img)


def visual_kind(question) -> str | None:
    """返回 'maze' / 'arc' / 'rect' / None（该题是否有图形化内容）。"""
    if not (question.source_info and question.source_info.type == "external"):
        return None
    task = (question.source_info.dataset_id or "").replace("task=", "")
    return {"maze": "maze", "arc_1d": "arc",
            "rectangle_count": "rect"}.get(task)


def render_question_png(question) -> bytes | None:
    kind = visual_kind(question)
    if kind == "maze":
        return render_maze(question)
    if kind == "arc":
        return render_arc(question)
    if kind == "rect":
        return render_rect(question)
    return None
