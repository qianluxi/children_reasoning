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
    assert client.get(f"/api/profile/{c1}").get_json()["total_attempts"] >= 1
    assert client.get(f"/api/profile/{c2}").get_json()["total_attempts"] == 0
