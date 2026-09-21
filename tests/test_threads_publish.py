import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
from zoneinfo import ZoneInfo
import pytest
import threads_publish as pub
import threads_client as tc

JST = ZoneInfo("Asia/Tokyo")
SCHEDULE = {"items": [
    {"key": "T001_20261001_0700", "publish_at": "2026-10-01T07:00:00+09:00",
     "text": "朝の投稿", "image_url": None, "reply_text": None},
    {"key": "T003_20261001_2100", "publish_at": "2026-10-01T21:00:00+09:00",
     "text": "夜の投稿", "image_url": "https://img/T003.png", "reply_text": "結論はこれ"},
]}
AM = datetime.datetime(2026, 10, 1, 7, 3, tzinfo=JST)
PM = datetime.datetime(2026, 10, 1, 21, 3, tzinfo=JST)


class FakeClient:
    ContainerError = tc.ContainerError

    def __init__(self, reply_fails=False):
        self.reply_fails = reply_fails
        self.created = []     # (text, image_url, reply_to_id)
        self.published = []

    def create_container(self, user_id, token, *, text, image_url=None, reply_to_id=None):
        if reply_to_id and self.reply_fails:
            raise tc.ContainerError("リプ失敗")
        self.created.append((text, image_url, reply_to_id))
        return f"C{len(self.created)}"

    def wait_for_container(self, token, cid):
        return None

    def publish_container(self, user_id, token, cid):
        self.published.append(cid)
        return f"POST_{cid}"


def test_run_テキストのみを公開しstateに記録する():
    c = FakeClient()
    st, key = pub.run(SCHEDULE, {}, AM, "U", "T", client=c)
    assert key == "T001_20261001_0700"
    assert c.created == [("朝の投稿", None, None)]
    assert c.published == ["C1"]
    e = st["T001_20261001_0700"]
    assert e["status"] == "published" and e["post_id"] == "POST_C1"
    assert "reply_id" not in e


def test_run_画像付きは自己リプまで出す():
    c = FakeClient()
    st, key = pub.run(SCHEDULE, {}, PM, "U", "T", client=c)
    assert key == "T003_20261001_2100"
    assert c.created[0] == ("夜の投稿", "https://img/T003.png", None)
    assert c.created[1] == ("結論はこれ", None, "POST_C1")
    assert st[key]["post_id"] == "POST_C1"
    assert st[key]["reply_id"] == "POST_C2"


def test_run_自己リプが失敗しても本体はpublishedとして残す():
    c = FakeClient(reply_fails=True)
    st, key = pub.run(SCHEDULE, {}, PM, "U", "T", client=c)
    assert st[key]["status"] == "published"
    assert st[key]["post_id"] == "POST_C1"
    assert st[key].get("reply_error")


def test_run_公開済みなら何もしない():
    c = FakeClient()
    st, key = pub.run(SCHEDULE, {"T001_20261001_0700": {"status": "published"}},
                      AM, "U", "T", client=c)
    assert key is None and c.published == []


def test_run_時刻が範囲外なら何もしない():
    c = FakeClient()
    far = datetime.datetime(2026, 10, 1, 14, 0, tzinfo=JST)
    st, key = pub.run(SCHEDULE, {}, far, "U", "T", client=c)
    assert key is None and c.created == []


def test_run_force_keyは窓を無視するが公開済みは飛ばさない():
    c = FakeClient()
    far = datetime.datetime(2026, 10, 5, 0, 0, tzinfo=JST)
    st, key = pub.run(SCHEDULE, {}, far, "U", "T", client=c, force_key="T001_20261001_0700")
    assert key == "T001_20261001_0700"
    st2, key2 = pub.run(SCHEDULE, st, far, "U", "T", client=c, force_key="T001_20261001_0700")
    assert key2 is None
