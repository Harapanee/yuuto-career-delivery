import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
import pytest
import threads_client as tc


def test_create_text_container():
    seen = {}

    def fake(method, path, params):
        seen["method"], seen["path"], seen["params"] = method, path, params
        return {"id": "C1"}

    assert tc.create_container("U", "T", text="本文", request=fake) == "C1"
    assert seen["method"] == "POST"
    assert seen["path"] == "U/threads"
    p = seen["params"]
    assert p["media_type"] == "TEXT"
    assert p["text"] == "本文"
    assert "image_url" not in p
    assert "reply_to_id" not in p


def test_create_image_container_はIMAGEでimage_urlを付ける():
    seen = {}
    tc.create_container("U", "T", text="本文", image_url="https://img",
                        request=lambda m, p, q: seen.update(q) or {"id": "C"})
    assert seen["media_type"] == "IMAGE"
    assert seen["image_url"] == "https://img"


def test_create_container_reply_to_idで自己リプになる():
    seen = {}
    tc.create_container("U", "T", text="補足", reply_to_id="P1",
                        request=lambda m, p, q: seen.update(q) or {"id": "C"})
    assert seen["reply_to_id"] == "P1"


def test_create_container_idが返らなければ例外():
    with pytest.raises(tc.ContainerError, match="コンテナ作成"):
        tc.create_container("U", "T", text="x",
                            request=lambda m, p, q: {"error": {"message": "boom"}})


def test_container_status_はstatusフィールドを読む():
    seen = {}

    def fake(m, p, q):
        seen["path"], seen["params"] = p, q
        return {"status": "FINISHED"}

    assert tc.container_status("T", "C1", request=fake) == "FINISHED"
    assert seen["path"] == "C1"
    assert "status" in seen["params"]["fields"]


def test_wait_for_container_FINISHEDで戻る():
    n = {"v": 0}

    def st(t, c, **kw):
        n["v"] += 1
        return "IN_PROGRESS" if n["v"] < 3 else "FINISHED"

    tc.wait_for_container("T", "C", status=st, sleep=lambda s: None)
    assert n["v"] == 3


def test_wait_for_container_ERRORで例外():
    with pytest.raises(tc.ContainerError, match="ERROR"):
        tc.wait_for_container("T", "C", status=lambda t, c, **k: "ERROR",
                              sleep=lambda s: None)


def test_publish_container():
    seen = {}

    def fake(m, p, q):
        seen["path"], seen["params"] = p, q
        return {"id": "POST9"}

    assert tc.publish_container("U", "T", "C1", request=fake) == "POST9"
    assert seen["path"] == "U/threads_publish"
    assert seen["params"]["creation_id"] == "C1"


def test_refresh_token_は新トークンと残日数を返す():
    seen = {}

    def fake(m, p, q):
        seen["path"], seen["params"] = p, q
        return {"access_token": "NEW", "expires_in": 5183933}

    tok, days = tc.refresh_token("OLD", request=fake)
    assert tok == "NEW" and days == 59
    assert seen["path"] == "refresh_access_token"
    assert seen["params"]["grant_type"] == "th_refresh_token"


def test_refresh_token_失敗なら例外():
    with pytest.raises(tc.ContainerError, match="更新"):
        tc.refresh_token("OLD", request=lambda m, p, q: {"error": {"message": "x"}})


def test_post_insights_はmetric名と値の辞書にする():
    res = {"data": [
        {"name": "views", "values": [{"value": 12}]},
        {"name": "likes", "values": [{"value": 3}]},
    ]}
    got = tc.post_insights("T", "P1", request=lambda m, p, q: res)
    assert got == {"views": 12, "likes": 3}


def test_publishing_limit():
    res = {"data": [{"quota_usage": 4, "config": {"quota_total": 250}}]}
    assert tc.publishing_limit("U", "T", request=lambda m, p, q: res) == (4, 250)
