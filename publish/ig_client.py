# -*- coding: utf-8 -*-
"""Instagram Graph API の投稿クライアント。

リールの投稿は3段階に分かれる。
  1. POST /{ig-user-id}/media          コンテナ作成(動画の取り込み)
  2. GET  /{container-id}              status_code が FINISHED になるまで待つ
  3. POST /{ig-user-id}/media_publish  公開

API に予約投稿は無いため、公開したい時刻に 3 を呼ぶしかない。
コンテナは作成から24時間有効なので、1と2は前倒しできる。
"""
import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.facebook.com/v22.0"


class ContainerError(Exception):
    """コンテナ作成・処理の失敗。メッセージにトークンを含めないこと"""


def _request(method, path, params):
    """トークンは params に入れて送る。例外メッセージにトークンを載せない"""
    if method == "POST":
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(f"{BASE}/{path}", data=data)
    else:
        req = urllib.request.Request(f"{BASE}/{path}?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode() or "{}"
        return json.loads(body)


def create_container(user_id, token, *, video_url, cover_url, caption,
                     audio_id, request=_request):
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token,
    }
    if cover_url:
        params["cover_url"] = cover_url
    if audio_id:
        params["audio_configuration"] = json.dumps(
            {"audio_id": audio_id, "audio_volume": 100, "video_volume": 0})
    res = request("POST", f"{user_id}/media", params)
    if "id" not in res:
        msg = res.get("error", {}).get("message", str(res))
        raise ContainerError(f"コンテナ作成に失敗した: {msg}")
    return res["id"]


def container_status(token, container_id, *, request=_request):
    res = request("GET", container_id,
                  {"fields": "status_code", "access_token": token})
    return res.get("status_code", "UNKNOWN")


def wait_for_container(token, container_id, *, interval=5, max_tries=60,
                       status=container_status, sleep=time.sleep):
    """FINISHED になるまで待つ。ERROR / EXPIRED / タイムアウトは例外"""
    for _ in range(max_tries):
        code = status(token, container_id)
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise ContainerError(f"コンテナの処理が失敗した: status_code={code}")
        sleep(interval)
    raise ContainerError(
        f"コンテナ処理がタイムアウトした({interval * max_tries}秒)")


def publish_container(user_id, token, container_id, *, request=_request):
    res = request("POST", f"{user_id}/media_publish",
                  {"creation_id": container_id, "access_token": token})
    if "id" not in res:
        msg = res.get("error", {}).get("message", str(res))
        raise ContainerError(f"公開に失敗した: {msg}")
    return res["id"]


def token_days_left(token, *, request=_request, now=None):
    """トークンの残日数。無期限なら None。判定できない場合も None"""
    res = request("GET", "debug_token",
                  {"input_token": token, "access_token": token})
    exp = res.get("data", {}).get("expires_at")
    if not exp:
        return None
    current = (now or (lambda: datetime.datetime.now(datetime.timezone.utc)))()
    expires = datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
    return (expires - current).days
