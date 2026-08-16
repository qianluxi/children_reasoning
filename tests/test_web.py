"""Web 层冒烟测试（使用 Flask 测试客户端，无需真实启动服务器）。"""
import pytest

from web.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def child_id(client):
    r = client.post("/api/children", json={"name": "web测试娃"})
    return r.get_json()["id"]


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/profile").status_code == 200


def test_child_create_and_list(client):
    r = client.post("/api/children", json={"name": "临时娃"})
    assert r.status_code == 200
    assert "id" in r.get_json()
    kids = client.get("/api/children").get_json()
    assert any(k["name"] == "临时娃" for k in kids)


def test_child_create_empty_rejected(client):
    r = client.post("/api/children", json={"name": "  "})
    assert r.status_code == 400


def test_next_question_no_leak(client, child_id):
    r = client.post("/api/next", json={"child_id": child_id})
    assert r.status_code == 200
    q = r.get_json()
    assert q["options"]
    # 关键：不能把答案/逻辑泄漏给前端
    assert "answer" not in q
    assert "option_logic" not in q
    assert "solution" not in q


def test_answer_and_profile(client, child_id):
    q = client.post("/api/next", json={"child_id": child_id}).get_json()
    # 用服务端知识找到正确答案（通过遍历选项判题接口）
    # 这里直接提交 choice=0，检查接口返回结构正确
    r = client.post("/api/answer", json={
        "child_id": child_id, "question_id": q["id"], "choice": 0})
    assert r.status_code == 200
    data = r.get_json()
    assert "correct" in data and "explanation" in data and "correct_text" in data

    prof = client.get(f"/api/profile/{child_id}").get_json()
    assert prof["total_attempts"] >= 1
    assert len(prof["skills"]) == 5


def test_hint_progressive(client, child_id):
    q = client.post("/api/next", json={"child_id": child_id}).get_json()
    r0 = client.get(f"/api/hint/{q['id']}?step=0").get_json()
    assert r0["hint"] is not None
    # 超出范围的 step 返回 None
    r_big = client.get(f"/api/hint/{q['id']}?step=99").get_json()
    assert r_big["hint"] is None


def test_answer_missing_question(client, child_id):
    client.post("/api/next", json={"child_id": child_id})  # 建立 session 身份
    r = client.post("/api/answer", json={
        "question_id": "nonexistent", "choice": 0})
    assert r.status_code == 404


# ---------- 专家审查 P1：API 参数与身份校验 ----------

def test_answer_requires_session():
    """没有先选儿童（无 session）就判题 → 400。"""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        r = c.post("/api/answer", json={"question_id": "x", "choice": 0})
        assert r.status_code == 400


def test_next_requires_real_child(client):
    r = client.post("/api/next", json={"child_id": 10 ** 9})
    assert r.status_code == 404
    r = client.post("/api/next", json={"child_id": "abc"})
    assert r.status_code == 400
    r = client.post("/api/next", json={})
    assert r.status_code == 400


def test_answer_choice_validation(client, child_id):
    q = client.post("/api/next", json={"child_id": child_id}).get_json()
    # 字符串 "0"、负数、越界、缺失 都必须被服务端拒绝
    for bad in ["0", -1, 999, None]:
        r = client.post("/api/answer", json={"question_id": q["id"], "choice": bad})
        assert r.status_code == 400, f"choice={bad!r} 应被拒绝"


def test_answer_qid_traversal_rejected(client, child_id):
    client.post("/api/next", json={"child_id": child_id})
    for qid in ["../../etc/passwd", "a/b", "..", "a.b", ""]:
        r = client.post("/api/answer", json={"question_id": qid, "choice": 0})
        assert r.status_code == 400, f"qid={qid!r} 应被拒绝"
    r = client.get("/api/hint/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in (400, 404)


def test_session_binds_child_blocks_forgery(client):
    """伪造请求体里的 child_id 无效：答题记录只能落在 session 绑定的儿童上。"""
    c1 = client.post("/api/children", json={"name": "绑定娃1"}).get_json()["id"]
    c2 = client.post("/api/children", json={"name": "绑定娃2"}).get_json()["id"]
    q = client.post("/api/next", json={"child_id": c1}).get_json()
    r = client.post("/api/answer", json={
        "child_id": c2, "question_id": q["id"], "choice": 0})
    assert r.status_code == 200
    # 记录落在 session 绑定的 c1；伪造的 c2 既没有记录、也无法查看档案（403）
    assert client.get(f"/api/profile/{c1}").get_json()["total_attempts"] >= 1
    assert client.get(f"/api/profile/{c2}").status_code == 403


def test_profile_blocks_other_child(client, child_id):
    """session 绑定儿童 A 后，读取儿童 B 的档案应 403（专家审查 P1）。"""
    other = client.post("/api/children", json={"name": "档案隔壁娃"}).get_json()["id"]
    client.post("/api/next", json={"child_id": child_id})  # session 绑定 child_id
    assert client.get(f"/api/profile/{child_id}").status_code == 200
    assert client.get(f"/api/profile/{other}").status_code == 403


# ---------- 专家意见 Phase 1：难度选择 ----------

def test_levels_api(client):
    r = client.get("/api/levels")
    assert r.status_code == 200
    lv = r.get_json()["levels"]
    assert [x["level"] for x in lv] == [1, 2, 3, 4]
    assert lv[0]["emoji"] == "🌱"
    assert lv[3]["label"] == "🧠 挑战"
    # 评分是内部信息，不能给儿童界面
    assert all("score" not in x for x in lv)


def test_next_with_level(client, child_id):
    r = client.post("/api/next", json={"child_id": child_id, "level": 2})
    assert r.status_code == 200
    q = r.get_json()
    assert q["difficulty_level"] in (1, 2, 3, 4)
    assert q["level_label"]
    assert "answer" not in q
    assert "option_logic" not in q


def test_next_with_category(client, child_id):
    r = client.post("/api/next", json={
        "child_id": child_id, "level": 2, "category": "ordering"})
    assert r.status_code == 200
    assert r.get_json()["type"] == "ordering"


def test_next_level_validation(client, child_id):
    for bad in (0, 5, -1, "2", True):
        r = client.post("/api/next", json={"child_id": child_id, "level": bad})
        assert r.status_code == 400, f"level={bad!r} 应被拒绝"
    r = client.post("/api/next", json={
        "child_id": child_id, "level": 2, "category": "不存在"})
    assert r.status_code == 400


def test_answer_with_time_ms(client, child_id):
    q = client.post("/api/next", json={"child_id": child_id}).get_json()
    r = client.post("/api/answer", json={
        "question_id": q["id"], "choice": 0, "time_ms": 1500})
    assert r.status_code == 200
    assert "correct" in r.get_json()


def test_answer_time_ms_validation(client, child_id):
    q = client.post("/api/next", json={"child_id": child_id}).get_json()
    for bad in (-1, "abc", 3.5, True, 3600_001):
        r = client.post("/api/answer", json={
            "question_id": q["id"], "choice": 0, "time_ms": bad})
        assert r.status_code == 400, f"time_ms={bad!r} 应被拒绝"


def test_attempt_records_time_and_score(client, child_id):
    """答题记录必须保存用时与难度分（专家意见第十七节）。"""
    import sqlite3
    from logic_kids.config import DB_PATH
    q = client.post("/api/next", json={
        "child_id": child_id, "level": 3}).get_json()
    r = client.post("/api/answer", json={
        "question_id": q["id"], "choice": 0, "time_ms": 999})
    assert r.status_code == 200
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT time_ms, difficulty_score FROM attempts "
            "WHERE child_id=? ORDER BY id DESC LIMIT 1", (child_id,)).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == 999
    assert row[1] is not None
