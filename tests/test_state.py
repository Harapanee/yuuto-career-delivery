import sys, os, json, tempfile, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
from zoneinfo import ZoneInfo
import pytest
import state

JST = ZoneInfo("Asia/Tokyo")


def test_load_ファイルが無ければ空辞書():
    assert state.load(os.path.join(tempfile.mkdtemp(), "nope.json")) == {}


def test_save_load_往復():
    p = os.path.join(tempfile.mkdtemp(), "state.json")
    state.save(p, {"day01_0600": {"status": "published"}})
    assert state.load(p) == {"day01_0600": {"status": "published"}}


def test_is_published():
    d = {"a": {"status": "published"}, "b": {"status": "prepared"}}
    assert state.is_published(d, "a") is True
    assert state.is_published(d, "b") is False
    assert state.is_published(d, "c") is False


def test_mark_prepared():
    d = state.mark_prepared({}, "k", "CID", "2026-09-01T00:02:41+09:00")
    assert d["k"]["status"] == "prepared"
    assert d["k"]["container_id"] == "CID"
    assert d["k"]["container_created_at"] == "2026-09-01T00:02:41+09:00"


def test_mark_published_既存のcontainer_idを消さない():
    d = state.mark_prepared({}, "k", "CID", "2026-09-01T00:02:41+09:00")
    d = state.mark_published(d, "k", "MID", "2026-09-01T06:03:12+09:00")
    assert d["k"]["status"] == "published"
    assert d["k"]["media_id"] == "MID"
    assert d["k"]["published_at"] == "2026-09-01T06:03:12+09:00"
    assert d["k"]["container_id"] == "CID"


def test_fresh_container_id_23時間以内なら返す():
    d = state.mark_prepared({}, "k", "CID", "2026-09-01T00:00:00+09:00")
    now = datetime.datetime(2026, 9, 1, 18, 0, tzinfo=JST)
    assert state.fresh_container_id(d, "k", now) == "CID"


def test_fresh_container_id_23時間を超えたらNone():
    d = state.mark_prepared({}, "k", "CID", "2026-09-01T00:00:00+09:00")
    now = datetime.datetime(2026, 9, 2, 0, 0, tzinfo=JST)   # 24時間後
    assert state.fresh_container_id(d, "k", now) is None


def test_fresh_container_id_記録が無ければNone():
    now = datetime.datetime(2026, 9, 1, 18, 0, tzinfo=JST)
    assert state.fresh_container_id({}, "k", now) is None


def test_save_書き込み中に失敗しても元のファイルが壊れない():
    """save() は一時ファイルに書いてから os.replace() で置き換える実装のはず。
    json.dump の途中で例外が起きても、置き換え前なので元のファイルは無傷でなければならない。
    実装をなぞらず、json.dump を壊して「途中で失敗したら元データが読めるか」を検証する。
    """
    d = tempfile.mkdtemp()
    p = os.path.join(d, "state.json")
    original = {"day01_0600": {"status": "published"}}
    state.save(p, original)

    def boom(*a, **k):
        raise RuntimeError("書き込み中にクラッシュした想定")

    real_dump = json.dump
    try:
        json.dump = boom
        with pytest.raises(RuntimeError):
            state.save(p, {"day01_0600": {"status": "broken"}})
    finally:
        json.dump = real_dump

    # 元のファイルは壊れず読める(二重投稿防止の記録が失われていない)
    assert state.load(p) == original
    # 一時ファイルが後片付けされている(ゴミが残っていない)
    leftovers = [f for f in os.listdir(d) if f != "state.json"]
    assert leftovers == []
