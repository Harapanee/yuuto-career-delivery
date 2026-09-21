# -*- coding: utf-8 -*-
"""Threads API の投稿クライアント。

投稿は IG と同じ2段階。テキストでも数秒 IN_PROGRESS になる(2026-09-22 実測)。
  1. POST /{user-id}/threads          コンテナ作成(media_type=TEXT|IMAGE)
  2. GET  /{container-id}?fields=status  FINISHED になるまで待つ
  3. POST /{user-id}/threads_publish  公開
自己リプは reply_to_id を付けて同じ手順。

トークンは「ユーザートークン生成ツール」の長期トークン(60日)。
th_exchange_token は通らず th_refresh_token だけ通る(2026-09-22 実測)。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.threads.net/v1.0"


class ContainerError(Exception):
    """API 失敗。メッセージにトークンを含めないこと"""


def _request(method, path, params):
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


def _error_message(res):
    return res.get("error", {}).get("message", str(res))


def create_container(user_id, token, *, text, image_url=None, reply_to_id=None,
                     request=_request):
    params = {"text": text, "access_token": token}
    if image_url:
        params["media_type"] = "IMAGE"
        params["image_url"] = image_url
    else:
        params["media_type"] = "TEXT"
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    res = request("POST", f"{user_id}/threads", params)
    if "id" not in res:
        raise ContainerError(f"コンテナ作成に失敗した: {_error_message(res)}")
    return res["id"]


def container_status(token, container_id, *, request=_request):
    res = request("GET", container_id,
                  {"fields": "status,error_message", "access_token": token})
    return res.get("status", "UNKNOWN")


def wait_for_container(token, container_id, *, interval=3, max_tries=40,
                       status=container_status, sleep=time.sleep):
    for _ in range(max_tries):
        code = status(token, container_id)
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise ContainerError(f"コンテナの処理が失敗した: status={code}")
        sleep(interval)
    raise ContainerError(f"コンテナ処理がタイムアウトした({interval * max_tries}秒)")


def publish_container(user_id, token, container_id, *, request=_request):
    res = request("POST", f"{user_id}/threads_publish",
                  {"creation_id": container_id, "access_token": token})
    if "id" not in res:
        raise ContainerError(f"公開に失敗した: {_error_message(res)}")
    return res["id"]


def refresh_token(token, *, request=_request):
    """長期トークンを更新する。(新トークン, 残日数) を返す。
    発行から24時間未満は失敗する。60日更新しないと失効し復旧不可"""
    res = request("GET", "refresh_access_token",
                  {"grant_type": "th_refresh_token", "access_token": token})
    if "access_token" not in res:
        raise ContainerError(f"トークン更新に失敗した: {_error_message(res)}")
    return res["access_token"], int(res.get("expires_in", 0)) // 86400


def post_insights(token, post_id, *, request=_request):
    res = request("GET", f"{post_id}/insights",
                  {"metric": "views,likes,replies,reposts,quotes,shares",
                   "access_token": token})
    out = {}
    for m in res.get("data", []):
        vals = m.get("values") or [{}]
        out[m["name"]] = vals[0].get("value", 0)
    return out


def publishing_limit(user_id, token, *, request=_request):
    """(使用数, 上限) を返す。24時間の移動枠"""
    res = request("GET", f"{user_id}/threads_publishing_limit",
                  {"fields": "quota_usage,config", "access_token": token})
    d = (res.get("data") or [{}])[0]
    return d.get("quota_usage", 0), d.get("config", {}).get("quota_total", 250)
