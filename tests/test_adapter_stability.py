"""适配层稳定性测试：畸形输入 / 网络失败 / 路径安全 / 幂等 / 批量压力。"""
import shutil
import urllib.request

import pytest

from logic_kids.bank import external, importer, provenance, store
from logic_kids.bank.sources import bigbench, logiqa
from logic_kids.config import IMPORTS_DIR, ensure_dirs
from logic_kids.validator.validator import validate


def _valid_bigbench_item(idx=0):
    return {
        "input": ("On a shelf, there are three books: a black book, an orange book, "
                  "and a blue book. The blue book is to the right of the orange book. "
                  "The orange book is to the right of the black book."),
        "target_scores": {
            "The black book is the leftmost.": 1,
            "The orange book is the leftmost.": 0,
            "The blue book is the leftmost.": 0,
        },
        "_task": "logical_deduction/three_objects", "_index": idx,
    }


@pytest.fixture(scope="module", autouse=True)
def isolated():
    ensure_dirs()
    store.clear()
    external.clear()
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    ensure_dirs()
    yield
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    store.clear()
    external.clear()


# ---------- 畸形输入 ----------

def test_bigbench_normalize_garbage():
    bads = [
        None, 42, "text", [], {},
        {"input": ""},
        {"input": "no colon here"},
        {"input": "A fruit stand sells two fruits: apples, and apples.",
         "target_scores": {"apples": 1}},
        {"input": "On a shelf, there are three books: a black book, a black book, "
                  "and a blue book. The blue book is to the right of the black book.",
         "target_scores": {"The black book is the leftmost.": 1,
                           "The blue book is the leftmost.": 0}},
    ]
    for bad in bads:
        assert bigbench.normalize(bad) is None, f"应拒绝: {bad!r}"


def test_logiqa_normalize_garbage():
    bads = [
        None, "x", 3, {},
        {"text": "t", "question": "q", "options": ["a"]},
        {"text": "t", "question": "q", "options": ["a", "b"], "answer": 9},
        {"text": "", "question": "q", "options": ["a", "b"], "answer": 0},
        {"text": "t", "question": "q", "options": ["a", "a"], "answer": 0},
    ]
    for bad in bads:
        assert logiqa.normalize(bad) is None, f"应拒绝: {bad!r}"


def test_logiqa_fetch_skips_bad_lines(monkeypatch):
    data = (b'{"example_id": 1, "answer": 0, "text": "t", "question": "q", '
            b'"options": ["a","b"]}\n[1,2,3]\nnot json\n'
            b'{"example_id": 2, "answer": 0, "text": "t", "question": "q", '
            b'"options": ["a","b"]}\n')

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return data

    monkeypatch.setattr(logiqa.urllib.request, "urlopen",
                        lambda url, timeout=None: FakeResp())
    items = logiqa.fetch(task="dev", lang="zh")
    assert len(items) == 2
    assert items[0]["_split"] == "dev" and items[0]["_lang"] == "zh"


def test_fetch_network_failure_raises_cleanly(monkeypatch):
    def boom(url, timeout=None):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(bigbench.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="下载失败"):
        bigbench.fetch(task="logical_deduction/three_objects")


# ---------- 路径安全 ----------

def test_external_load_question_any_traversal_safe():
    for qid in ("../../etc/passwd", "..", "a/b", "..%2F..%2Fetc", ""):
        assert external.load_question_any(qid) is None
    assert provenance.load_pending("../../etc/passwd") is None


def test_source_slug_sanitizes_weird_names():
    assert external.source_slug("Weird 名称!@#123") == "weird123"
    assert external.source_slug("A.B/C") == "abc"


# ---------- 索引损坏 ----------

def test_external_corrupt_index_raises():
    from logic_kids.bank.external import source_dir
    source_dir("zzz").mkdir(parents=True, exist_ok=True)
    (source_dir("zzz") / "index.json").write_text('{"broken": ', encoding="utf-8")
    with pytest.raises(RuntimeError):
        external._index("zzz")
    shutil.rmtree(source_dir("zzz"))


# ---------- 批量导入：幂等 + 一致性 + 压力 ----------

def test_import_rejects_garbage_without_crash():
    items = [_valid_bigbench_item(0), None, "bad", {}, _valid_bigbench_item(1)]
    report = importer.import_items("bigbench", items, bigbench.normalize)
    assert report["total"] == 5
    assert report["translated"] == 2
    assert report["skipped"] == 3


def test_duplicate_qid_deduped_within_batch():
    items = [_valid_bigbench_item(0), _valid_bigbench_item(0)]
    report = importer.import_items("bigbench", items, bigbench.normalize)
    assert report["total"] == 2
    assert report["pending"] == 1


def test_stress_import_approve_consistency():
    """批量压力：30 个变体全部过闸门、可审核入库，且库内一致性完好。"""
    external.clear()
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    ensure_dirs()
    items = [_valid_bigbench_item(i) for i in range(30)]
    report = importer.import_items("bigbench", items, bigbench.normalize,
                                   translate=bigbench.zh_translate_question)
    assert report["pending"] == 30
    ok_n, fail_n, failures = importer.approve_all_pending()
    assert fail_n == 0, failures[:3]
    assert ok_n == 30
    assert external.stats()["total"] == 30

    # 库内一致性：索引 ↔ 文件、每题通过 Validator、标签齐全
    slug_dir = external.source_dir("bigbench")
    files = {p.stem for p in slug_dir.glob("*.json") if p.name != "index.json"}
    assert set(external.list_ids("bigbench")) == files
    for qid in external.list_ids("bigbench"):
        q = external.load_question("bigbench", qid)
        assert validate(q).ok
        assert q.category and q.skills
        assert q.age_range in ("A", "B", "C", "D")
        assert q.difficulty_profile
        assert q.translations and "zh" in q.translations
        assert q.provenance.review_status == "approved"


def test_reimport_is_idempotent():
    """同一批题重复导入：pending 与外部库数量不翻倍。"""
    items = [_valid_bigbench_item(i) for i in range(3)]
    importer.import_items("bigbench", items, bigbench.normalize)
    importer.import_items("bigbench", items, bigbench.normalize)
    pending = [p for p in provenance.list_pending()
               if p["review_status"] == "pending"]
    assert len(pending) == 3
