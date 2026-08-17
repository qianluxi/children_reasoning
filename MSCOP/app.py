"""小小推理家 · ModelScope 创空间版（Gradio）。

儿童化界面：选挑战类型（能力卡片）→ 选难度 → 答题（图形题自动显示图片）。
外部题库已随 data/external 打包，内置题库在启动时自动生成。
"""
from __future__ import annotations

from io import BytesIO

import gradio as gr
from PIL import Image

from logic_kids import taxonomy, visuals
from logic_kids.bank import seed, store
from logic_kids.difficulty import engine
from logic_kids.questions.generator import generate_batch, TYPE_NAMES
from logic_kids.questions.selector import select_question
from logic_kids.progress import store as progress

# 儿童挑战卡片：只暴露能力，不暴露数据源
CHALLENGES = {
    "🧠 综合挑战": None,
    "🧩 逻辑推理": "deduction",
    "🔍 找规律": "pattern",
    "🔢 数学思维": "math",
    "🧭 空间迷宫": "spatial",
    "🪢 关系推理": "relation",
    "📏 排序挑战": "ordering",
}

LEVELS = [("🌱 简单", 1), ("⭐ 普通", 2), ("🚀 困难", 3), ("🧠 挑战", 4)]


def _ensure_bank():
    """内置题库为空时自动生成（外部题库已打包在 data/external）。"""
    if store.stats()["total"] == 0:
        seeds = seed.validated_seeds()
        for q in seeds:
            engine.apply(q)
        store.save_many(seeds)
        store.save_many(generate_batch(60, seed=2024))


_ensure_bank()


def _session() -> dict:
    return {"child_id": progress.get_or_create_child("小玩家"),
            "q": None, "options_zh": [], "hint": 0, "answered": False,
            "level": 2, "ability": None}


state = gr.State(_session())


def _zh(q):
    tr = q.translations or {}
    return tr.get("zh_child") or tr.get("zh")


def _question_view():
    q = state.value.get("q")
    state.value["hint"] = 0
    state.value["answered"] = False
    zh = _zh(q)
    story = zh.get("story_text", q.story.text) if zh else q.story.text
    prompt = zh.get("question_prompt", q.question_prompt) if zh \
        else q.question_prompt
    options = list(zh.get("options", q.options)) if zh else list(q.options)
    state.value["options_zh"] = options
    title = f"《{q.story.title}》｜{taxonomy.ability_label(q.category)} · " \
            f"{TYPE_NAMES.get(q.type, q.type)}"
    info = f"**{title}**\n\n{story}"
    img = None
    data = visuals.render_question_png(q)
    if data:
        img = Image.open(BytesIO(data))
    return (info, img, gr.update(choices=options, value=None), prompt,
            "", "提交答案", gr.update(visible=False), state)


def start(challenge, level):
    state.value["ability"] = CHALLENGES.get(challenge)
    state.value["level"] = level
    pick = select_question(difficulty=level, child_id=state.value["child_id"],
                           mixed=True, category=state.value["ability"])
    if pick is None:
        return ("暂无合适的题目，请换个挑战或难度", None,
                gr.update(choices=[]), "", "", "提交答案",
                gr.update(visible=False), state)
    state.value["q"] = pick["question"]
    return _question_view()


def next_question():
    pick = select_question(difficulty=state.value["level"],
                           child_id=state.value["child_id"], mixed=True,
                           category=state.value["ability"])
    if pick is None:
        return ("暂无合适的题目，请换个挑战或难度", None,
                gr.update(choices=[]), "", "", "提交答案",
                gr.update(visible=False), state)
    state.value["q"] = pick["question"]
    return _question_view()


def submit(answer):
    q = state.value.get("q")
    if q is None:
        return "请先点击「开始挑战」", gr.update(visible=False)
    if state.value.get("answered"):
        return "这题已经答过啦，点「下一题」继续吧！", gr.update(visible=False)
    if answer is None:
        return "请先选择一个答案～", gr.update(visible=False)
    try:
        idx = state.value["options_zh"].index(answer)
    except ValueError:
        return "答案无效，请重新选择", gr.update(visible=False)
    correct = idx == q.answer
    state.value["answered"] = True
    progress.record_attempt(state.value["child_id"], q.id, q.type, correct,
                            category=q.category)
    zh = _zh(q)
    explanation = zh.get("explanation", q.explanation) if zh else q.explanation
    correct_text = state.value["options_zh"][q.answer]
    if correct:
        fb = f"🎉 答对啦！你真棒！\n\n{explanation}"
    else:
        fb = f"💪 再想想～正确答案是：**{correct_text}**\n\n{explanation}"
    return fb, gr.update(visible=True)


def show_hint():
    q = state.value.get("q")
    if q is None or state.value.get("answered"):
        return ""
    step = state.value.get("hint", 0)
    if step >= len(q.hints):
        return "没有更多提示啦，再想想～"
    state.value["hint"] = step + 1
    return "💡 " + q.hints[step]


with gr.Blocks(title="小小推理家 · 儿童思维训练") as demo:
    gr.Markdown("# 🧠 小小推理家 · 儿童思维训练\n"
                "选一个挑战类型和难度，开始今天的逻辑冒险吧！")
    with gr.Row():
        challenge = gr.Dropdown(list(CHALLENGES), value="🧠 综合挑战",
                                label="挑战类型")
        level = gr.Radio(LEVELS, value=2, label="难度", type="value")
    start_btn = gr.Button("🚀 开始挑战", variant="primary")
    info = gr.Markdown()
    img = gr.Image(type="pil", label="题目图形", visible=False)
    prompt = gr.Markdown()
    opts = gr.Radio(choices=[], label="你的答案")
    submit_btn = gr.Button("提交答案")
    fb = gr.Markdown()
    with gr.Row():
        hint_btn = gr.Button("💡 提示")
        next_btn = gr.Button("下一题 →", visible=False)
    hint_txt = gr.Markdown()

    start_btn.click(start, [challenge, level],
                    [info, img, opts, prompt, fb, submit_btn, next_btn, state])
    next_btn.click(next_question, None,
                   [info, img, opts, prompt, fb, submit_btn, next_btn, state])
    submit_btn.click(submit, [opts], [fb, next_btn])
    hint_btn.click(show_hint, None, [hint_txt])


if __name__ == "__main__":
    demo.queue().launch()
