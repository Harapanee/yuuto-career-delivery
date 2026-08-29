import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
import pytest
import ig_client


def test_create_container_必要なパラメータを渡す():
    seen = {}

    def fake(method, path, params):
        seen["method"], seen["path"], seen["params"] = method, path, params
        return {"id": "CID123"}

    got = ig_client.create_container(
        "IG", "T", video_url="https://v", cover_url="https://c",
        caption="本文", audio_id="A1", request=fake)

    assert got == "CID123"
    assert seen["method"] == "POST"
    assert seen["path"] == "IG/media"
    p = seen["params"]
    assert p["media_type"] == "REELS"
    assert p["video_url"] == "https://v"
    assert p["cover_url"] == "https://c"
    assert p["caption"] == "本文"
    assert p["share_to_feed"] == "true"
    import json as _j
    assert _j.loads(p["audio_configuration"]) == {
        "audio_id": "A1", "audio_volume": 100, "video_volume": 0}


def test_create_container_audio_idがNoneなら音源を付けない():
    seen = {}

    def fake(method, path, params):
        seen.update(params); return {"id": "C"}

    ig_client.create_container("IG", "T", video_url="v", cover_url="c",
                               caption="x", audio_id=None, request=fake)
    assert "audio_configuration" not in seen


def test_create_container_idが返らなければ例外():
    with pytest.raises(ig_client.ContainerError, match="コンテナ作成"):
        ig_client.create_container("IG", "T", video_url="v", cover_url="c",
                                   caption="x", audio_id=None,
                                   request=lambda m, p, q: {"error": {"message": "boom"}})


def test_container_status():
    got = ig_client.container_status(
        "T", "CID", request=lambda m, p, q: {"status_code": "FINISHED"})
    assert got == "FINISHED"


def test_wait_for_container_FINISHEDで戻る():
    calls = {"n": 0}

    def fake_status(token, cid, **kw):
        calls["n"] += 1
        return "IN_PROGRESS" if calls["n"] < 3 else "FINISHED"

    ig_client.wait_for_container("T", "CID", status=fake_status,
                                 sleep=lambda s: None)
    assert calls["n"] == 3


def test_wait_for_container_ERRORで例外():
    with pytest.raises(ig_client.ContainerError, match="ERROR"):
        ig_client.wait_for_container("T", "CID",
                                     status=lambda t, c, **k: "ERROR",
                                     sleep=lambda s: None)


def test_wait_for_container_タイムアウトで例外():
    with pytest.raises(ig_client.ContainerError, match="タイムアウト"):
        ig_client.wait_for_container("T", "CID", max_tries=2,
                                     status=lambda t, c, **k: "IN_PROGRESS",
                                     sleep=lambda s: None)


def test_publish_container():
    seen = {}

    def fake(method, path, params):
        seen["path"] = path; seen["params"] = params
        return {"id": "MEDIA9"}

    got = ig_client.publish_container("IG", "T", "CID", request=fake)
    assert got == "MEDIA9"
    assert seen["path"] == "IG/media_publish"
    assert seen["params"]["creation_id"] == "CID"


def test_token_days_left():
    now = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
    exp = int(datetime.datetime(2026, 9, 21,
                                tzinfo=datetime.timezone.utc).timestamp())
    got = ig_client.token_days_left(
        "T", request=lambda m, p, q: {"data": {"expires_at": exp}}, now=lambda: now)
    assert got == 20


def test_token_days_left_無期限ならNone():
    got = ig_client.token_days_left(
        "T", request=lambda m, p, q: {"data": {"expires_at": 0}})
    assert got is None
