"""Flask Web 应用（儿童交互层，专家意见第十四节）。

设计原则：
  · 前端只拿到"表现层"数据（故事、陈述、选项文字），绝不泄漏 answer / option_logic；
  · 判题在服务端完成（POST /api/answer）；
  · 提示逐步发放（GET /api/hint），引导而不直接给答案。
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from logic_kids.bank import store, seed
from logic_kids.difficulty import engine as difficulty_engine
from logic_kids.progress import store as progress
from logic_kids.engine import adaptive
from logic_kids.questions.generator import generate_batch, TYPE_NAMES

WEB_DIR = Path(__file__).resolve().parent


def _public_question(q) -> dict:
    """去掉答案与逻辑，只给儿童看的表现层。"""
    return {
        "id": q.id,
        "type": q.type,
        "type_name": TYPE_NAMES.get(q.type, q.type),
        "difficulty": q.difficulty,
        "stars": "★" * q.difficulty,
        "story": {"title": q.story.title, "text": q.story.text},
        "statements": [
            {"speaker": q.story.roles.get(s.speaker, s.speaker or ""), "text": s.text}
            for s in q.statements
        ],
        "constraints": [c.text for c in q.constraints if c.text],
        "question_prompt": q.question_prompt,
        "options": list(q.options),
        "hint_count": len(q.hints),
    }


def _ensure_bank():
    """首次运行时自动载入种子题并生成一批题目。"""
    if store.stats()["total"] > 0:
        return
    seeds = seed.all_seeds()
    for q in seeds:
        difficulty_engine.apply(q)
    store.save_many(seeds)
    store.save_many(generate_batch(40, seed=2024))


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(WEB_DIR / "templates"),
        static_folder=str(WEB_DIR / "static"),
    )
    _ensure_bank()

    # ---------- 页面 ----------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/profile")
    def profile_page():
        return render_template("profile.html")

    # ---------- 儿童 ----------
    @app.route("/api/children", methods=["GET"])
    def list_children():
        return jsonify(progress.list_children())

    @app.route("/api/children", methods=["POST"])
    def create_child():
        name = (request.get_json(force=True) or {}).get("name", "").strip()
        if not name:
            return jsonify({"error": "名字不能为空"}), 400
        cid = progress.get_or_create_child(name)
        return jsonify({"id": cid, "name": name})

    # ---------- 出题 ----------
    @app.route("/api/next", methods=["POST"])
    def next_question():
        data = request.get_json(force=True) or {}
        child_id = data.get("child_id")
        if not child_id:
            return jsonify({"error": "缺少 child_id"}), 400
        pick = adaptive.next_question(int(child_id))
        if pick is None:
            return jsonify({"error": "题库空了"}), 404
        resp = _public_question(pick["question"])
        resp["reason"] = pick["reason"]
        return jsonify(resp)

    # ---------- 判题 ----------
    @app.route("/api/answer", methods=["POST"])
    def answer():
        data = request.get_json(force=True) or {}
        child_id = data.get("child_id")
        qid = data.get("question_id")
        choice = data.get("choice")
        q = store.load_question(qid)
        if q is None:
            return jsonify({"error": "题目不存在"}), 404
        correct = (choice == q.answer)
        if child_id:
            progress.record_attempt(int(child_id), q.id, q.type, correct)
        return jsonify({
            "correct": correct,
            "correct_index": q.answer,
            "correct_text": q.options[q.answer],
            "explanation": q.explanation,
        })

    # ---------- 提示（逐步） ----------
    @app.route("/api/hint/<qid>")
    def hint(qid):
        step = request.args.get("step", 0, type=int)
        q = store.load_question(qid)
        if q is None:
            return jsonify({"error": "题目不存在"}), 404
        if step < 0 or step >= len(q.hints):
            return jsonify({"hint": None})
        return jsonify({"hint": q.hints[step], "step": step,
                        "has_more": step + 1 < len(q.hints)})

    # ---------- 能力画像 ----------
    @app.route("/api/profile/<int:child_id>")
    def profile(child_id):
        prof = progress.profile(child_id, list(TYPE_NAMES))
        # 转成前端友好的列表
        rows = []
        for t, info in prof.items():
            m = info["mastery"]
            rows.append({
                "type": t,
                "type_name": TYPE_NAMES.get(t, t),
                "mastery": None if m is None else round(m * 100),
                "attempts": info["attempts"],
            })
        return jsonify({
            "skills": rows,
            "total_attempts": progress.total_attempts(child_id),
            "stars": progress.stars_earned(child_id),
        })

    return app
