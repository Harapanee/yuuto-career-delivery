#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI から実際に Instagram Graph API を叩いて、投稿できる状態かを確認する。

★これを用意した理由:
  publish.py は「予定時刻の±90分の外なら何もしない」ため、
  予定が無い日に CI を回しても **一度もAPIを叩かないまま緑になる。**
  実際にそれで API ホストの誤りが本番投入をすり抜けた事例がある(しゅうとキャリア 2026-08-29)。
  投稿経路に手を入れたら、必ずこれを CI 上で通してから量産に入ること。

副作用のある呼び出しは一切しない(読み取りのみ)。
トークンの残日数も出し、閾値を切ったら警告する。
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import datetime

BASE = "https://graph.facebook.com/v22.0"
WARN_DAYS = 14


def get(path, token, **params):
    params["access_token"] = token
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    user_id = os.environ.get("IG_USER_ID", "")
    if not token or not user_id:
        sys.exit("IG_ACCESS_TOKEN / IG_USER_ID が設定されていない")

    # トークンの発行方式とホストの対応を最初に確認する。
    # EAA... = Facebook Login → graph.facebook.com / IGAA... = Instagram Login → graph.instagram.com
    # 食い違うと code 190 が返る。失効エラーと紛らわしいので先にここで弾く。
    if not token.startswith("EAA"):
        sys.exit(f"トークンが EAA で始まっていない(先頭 {token[:4]!r})。"
                 "このリポジトリは graph.facebook.com を使うので Facebook Login のトークンが要る")
    print("トークンの先頭: EAA → ホスト graph.facebook.com で正しい")

    me = get("me", token, fields="id,name")
    print(f"/me                     : {me['name']} ({me['id']})")

    ig = get(user_id, token, fields="id,username,media_count")
    print(f"/{{IG_USER_ID}}           : @{ig['username']} / 投稿数 {ig['media_count']}")

    limit = get(f"{user_id}/content_publishing_limit", token)
    used = limit["data"][0].get("quota_usage", "?")
    print(f"content_publishing_limit: quota_usage={used}  ← 投稿権限が実際に効いている")

    dbg = get("debug_token", token, input_token=token)["data"]
    exp = dbg.get("expires_at", 0)
    if exp:
        left = (datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
                - datetime.datetime.now(datetime.timezone.utc)).days
        when = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
        print(f"トークン失効            : {when} (残り {left} 日)")
        if left <= WARN_DAYS:
            print(f"::warning::トークンの残りが {left} 日です。更新しないと無言で投稿が止まります。"
                  "更新手順は制作リポジトリの HANDOFF.md 冒頭。")
    else:
        print("トークン失効            : 無期限")
    print(f"scopes                  : {', '.join(dbg.get('scopes', []))}")

    need = {"instagram_basic", "instagram_content_publish"}
    missing = need - set(dbg.get("scopes", []))
    if missing:
        sys.exit(f"必要な権限が足りない: {', '.join(sorted(missing))}")
    print("\n疎通確認: すべて通過")


if __name__ == "__main__":
    main()
