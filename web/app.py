"""Flask Web 应用（儿童交互层，专家意见第十四节）。

设计原则：
  · 前端只拿到"表现层"数据（故事、陈述、选项文字），绝不泄漏 answer / option_logic；
  · 判题在服务端完成（POST /api/answer）；
  · 提示逐步发放（GET /api/hint），引导而不直接给答案。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from logic_kids.bank import external, store, seed
from logic_kids.difficulty import engine as difficulty_engine, levels as difficulty_levels
from logic_kids.progress import store as progress
from logic_kids.engine import adaptive
from logic_kids.questions.generator import generate_batch, TYPE_NAMES, GENERATORS
from logic_kids.questions.selector import select_question
from logic_kids import taxonomy

WEB_DIR = Path(__file__).resolve().parent

# 题目 id 白名单（专家审查：防止路径穿越）
_QID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _public_question(q, lang: str = "zh") -> dict:
    """去掉答案与逻辑，只给儿童看的表现层。"""
    is_external = bool(q.source_info and q.source_info.type == "external")
    zh = (q.translations or {}).get("zh") if q.translations else None
    use_zh = lang == "zh" and zh is not None
    constraints = (zh["constraints"] if use_zh
                   else [c.text for c in q.constraints if c.text])
    options = zh["options"] if use_zh else list(q.options)
    story_title = zh["story_title"] if use_zh else q.story.title
    story_text = zh["story_text"] if use_zh else q.story.text
    prompt = zh.get("question_prompt", q.question_prompt) if use_zh \
        else q.question_prompt
    resp = {
        "id": q.id,
        "type": q.type,
        "type_name": TYPE_NAMES.get(q.type, q.type),
        "bank": "external" if is_external else "builtin",
        "source_name": q.source_info.name if is_external else "",
        "lang": "zh" if use_zh else "en",
        "category": q.category,
        "category_name": taxonomy.ability_label(q.category),
        "skills": [{"id": s, "name": taxonomy.skill_label(s)}
                   for s in (q.skills or [])],
        "age_range": q.age_range,
        "difficulty": q.difficulty,
        "difficulty_level": q.difficulty_level
        or difficulty_levels.level_for_score(q.difficulty_score),
        "level_label": q.level_label(),
        "stars": "★" * q.difficulty,
        "story": {"title": story_title, "text": story_text},
        "statements": [
            {"speaker": q.story.roles.get(s.speaker, s.speaker or ""), "text": s.text}
            for s in q.statements
        ],
        "constraints": constraints,
        "question_prompt": prompt,
        "options": options,
        "hint_count": len(q.hints),
    }
    return resp


def _ensure_bank():
    """首次运行时自动载入种子题并生成一批题目。

    种子题必须先过 Validator 才能入库（seed → validate → difficulty → save），
    与 CLI 入口共用 validated_seeds()，防止人工改坏种子题后绕过检查。
    """
    if store.stats()["total"] > 0:
        return
    seeds = seed.validated_seeds()
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
    # session 签名密钥（仅限本地开发默认值；部署公网前必须设置 SECRET_KEY）
    if os.environ.get("SECRET_KEY") is None:
        print("[warn] 未设置 SECRET_KEY 环境变量，正在使用默认密钥——仅限本地开发，部署公网前必须设置")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
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
    @app.route("/api/levels")
    def levels_api():
        """难度等级清单（前端只拿等级名，不拿评分）。"""
        return jsonify({"levels": difficulty_levels.public_levels()})

    @app.route("/api/external/sources")
    def external_sources():
        """外部题库来源清单（名称/许可证/题数），前端按来源选择。"""
        return jsonify({"sources": external.list_sources()})

    @app.route("/api/next", methods=["POST"])
    def next_question():
        data = request.get_json(force=True) or {}
        child_id = data.get("child_id")
        # 参数校验：child_id 必须是正整数且真实存在（专家审查 P1）
        if not isinstance(child_id, int) or isinstance(child_id, bool) or child_id <= 0:
            return jsonify({"error": "child_id 必须是正整数"}), 400
        if not progress.child_exists(child_id):
            return jsonify({"error": "儿童不存在"}), 404
        # 可选参数：题库模式（内置/外部）、外部来源、难度等级（1..4）、题型
        level = data.get("level")
        category = data.get("category")
        bank = data.get("bank", "builtin")
        source = data.get("source")
        lang = data.get("lang", "zh")
        if lang not in ("zh", "en"):
            return jsonify({"error": "lang 必须是 zh 或 en"}), 400
        if bank not in ("builtin", "external"):
            return jsonify({"error": "bank 必须是 builtin 或 external"}), 400
        if bank == "external":
            known = {s["slug"] for s in external.list_sources()}
            if source is not None and source not in known:
                return jsonify({"error": f"未知外部题库来源：{source}"}), 400
        if level is not None:
            try:
                level = difficulty_levels.validate_level(level)
            except ValueError:
                return jsonify({"error": "难度等级必须是 1~4 的整数"}), 400
        if category is not None:
            if not isinstance(category, str) or category not in GENERATORS:
                return jsonify({"error": f"未知题型，可选：{', '.join(TYPE_NAMES)}"}), 400
        # 身份绑定：本次浏览器的 session 只认这个儿童
        session["child_id"] = child_id
        session["lang"] = lang
        if bank == "external":
            pick = select_question(difficulty=level, child_id=child_id,
                                   category=category, external_bank=True,
                                   source=source)
        elif level is not None:
            pick = select_question(difficulty=level, child_id=child_id,
                                   category=category)
        else:
            pick = adaptive.next_question(child_id)
        if pick is None:
            return jsonify({"error": "该题库暂无可用题目"}), 404
        resp = _public_question(pick["question"], lang)
        resp["reason"] = pick["reason"]
        return jsonify(resp)

    # ---------- 判题 ----------
    @app.route("/api/answer", methods=["POST"])
    def answer():
        # 身份来自 session（忽略请求体里的 child_id，防止伪造换人）
        child_id = session.get("child_id")
        if child_id is None or not progress.child_exists(child_id):
            return jsonify({"error": "请先选择儿童"}), 400
        data = request.get_json(force=True) or {}
        qid = data.get("question_id")
        if not isinstance(qid, str) or not _QID_RE.fullmatch(qid):
            return jsonify({"error": "题目编号不合法"}), 400
        q = store.load_question(qid) or external.load_question_any(qid)
        if q is None:
            return jsonify({"error": "题目不存在"}), 404
        choice = data.get("choice")
        # 参数校验：choice 必须是 int 且在选项范围内（专家审查 P1）
        if not isinstance(choice, int) or isinstance(choice, bool) or not (0 <= choice < len(q.options)):
            return jsonify({"error": "选项编号超出范围"}), 400
        # 解题时间（专家意见第十七节：正确率 + 用时才能反映真实能力）
        time_ms = data.get("time_ms")
        if time_ms is not None:
            if isinstance(time_ms, bool) or not isinstance(time_ms, int) \
                    or time_ms < 0 or time_ms > 3600_000:
                return jsonify({"error": "time_ms 必须是 0..3600000 的整数"}), 400
        correct = (choice == q.answer)
        progress.record_attempt(child_id, q.id, q.type, correct,
                                time_ms=time_ms,
                                difficulty_score=q.difficulty_score,
                                category=q.category)
        zh = (q.translations or {}).get("zh") if q.translations else None
        explanation = zh["explanation"] if session.get("lang") == "zh" and zh \
            else q.explanation
        options = zh["options"] if session.get("lang") == "zh" and zh \
            else q.options
        return jsonify({
            "correct": correct,
            "correct_index": q.answer,
            "correct_text": options[q.answer],
            "explanation": explanation,
        })

    # ---------- 提示（逐步） ----------
    @app.route("/api/hint/<qid>")
    def hint(qid):
        if not _QID_RE.fullmatch(qid):
            return jsonify({"error": "题目编号不合法"}), 400
        step = request.args.get("step", 0, type=int)
        q = store.load_question(qid) or external.load_question_any(qid)
        if q is None:
            return jsonify({"error": "题目不存在"}), 404
        if step < 0 or step >= len(q.hints):
            return jsonify({"hint": None})
        return jsonify({"hint": q.hints[step], "step": step,
                        "has_more": step + 1 < len(q.hints)})

    # ---------- 能力画像 ----------
    @app.route("/api/profile/<int:child_id>")
    def profile(child_id):
        # 身份校验（专家审查 P1）：session 已绑定儿童时只能查看自己的档案
        session_child = session.get("child_id")
        if session_child is not None and session_child != child_id:
            return jsonify({"error": "只能查看当前登录儿童的档案"}), 403
        # 能力画像只展示 5 个核心题型（外部导入题不参与能力建模）
        prof = progress.profile(child_id, list(GENERATORS))
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
        abilities = progress.ability_profile(child_id)
        ability_rows = [{
            "ability": cat,
            "name": taxonomy.ability_label(cat),
            "emoji": taxonomy.ability_emoji(cat),
            "mastery": None if info["mastery"] is None
                       else round(info["mastery"] * 100),
            "attempts": info["attempts"],
        } for cat, info in sorted(abilities.items())]
        return jsonify({
            "skills": rows,
            "abilities": ability_rows,
            "total_attempts": progress.total_attempts(child_id),
            "stars": progress.stars_earned(child_id),
        })

    return app
