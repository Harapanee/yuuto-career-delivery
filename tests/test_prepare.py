import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
from zoneinfo import ZoneInfo
import prepare, ig_client

JST = ZoneInfo("Asia/Tokyo")
SCHEDULE = {"items": [
    {"key": "day01_0600", "publish_at": "2026-09-01T06:00:00+09:00",
     "video_url": "v1", "cover_url": "c1", "caption": "本文1", "audio_id": "A1"},
    {"key": "day01_1200", "publish_at": "2026-09-01T12:00:00+09:00",
     "video_url": "v2", "cover_url": "c2", "caption": "本文2", "audio_id": "A2"},
]}
NOW = datetime.datetime(2026, 9, 1, 0, 5, tzinfo=JST)


class FakeClient:
    ContainerError = ig_client.ContainerError

    def __init__(self, fail_keys=()):
        self.fail_keys = set(fail_keys)
        self.created = []

    def create_container(self, user_id, token, *, video_url, cover_url,
                         caption, audio_id):
        if video_url in self.fail_keys:
            raise ig_client.ContainerError("失敗")
        self.created.append(video_url)
        return f"CID_{video_url}"

    def wait_for_container(self, token, container_id):
        return None


def test_run_その日の全件のコンテナを作る():
    c = FakeClient()
    st, failed = prepare.run(SCHEDULE, {}, NOW, "IG", "T", client=c)
    assert failed == []
    assert st["day01_0600"]["status"] == "prepared"
    assert st["day01_0600"]["container_id"] == "CID_v1"
    assert st["day01_1200"]["container_id"] == "CID_v2"
    assert c.created == ["v1", "v2"]


def test_run_公開済みは飛ばす():
    c = FakeClient()
    st, failed = prepare.run(SCHEDULE, {"day01_0600": {"status": "published"}},
                             NOW, "IG", "T", client=c)
    assert c.created == ["v2"]
    assert failed == []


def test_run_準備済みは飛ばす():
    existing = {"day01_0600": {"status": "prepared", "container_id": "OLD",
                               "container_created_at": "2026-09-01T00:00:00+09:00"}}
    c = FakeClient()
    st, failed = prepare.run(SCHEDULE, existing, NOW, "IG", "T", client=c)
    assert c.created == ["v2"]
    assert st["day01_0600"]["container_id"] == "OLD"


def test_run_失敗しても残りを処理し失敗キーを返す():
    c = FakeClient(fail_keys={"v1"})
    st, failed = prepare.run(SCHEDULE, {}, NOW, "IG", "T", client=c)
    assert failed == ["day01_0600"]
    assert c.created == ["v2"]
    assert st["day01_1200"]["status"] == "prepared"
    assert "day01_0600" not in st


def test_run_該当日が無ければ何もしない():
    c = FakeClient()
    other = datetime.datetime(2026, 12, 1, 0, 5, tzinfo=JST)
    st, failed = prepare.run(SCHEDULE, {}, other, "IG", "T", client=c)
    assert st == {} and failed == [] and c.created == []
