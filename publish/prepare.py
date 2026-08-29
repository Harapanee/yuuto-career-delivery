# -*- coding: utf-8 -*-
"""0時フェーズ: その日の分のコンテナを事前に作る(@yuuto.career は1日2本)。

重い処理(動画の取り込みとポーリング)をここで済ませることで、
定時の処理は media_publish 1回だけになり、
失敗も投稿時刻の数時間前に検知できる。
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

import ig_client
import schedule_select
import state as state_mod

JST = ZoneInfo("Asia/Tokyo")


def run(schedule, state_data, now, user_id, token, *, client=ig_client):
    """その日の未処理エントリのコンテナを作る。(更新後state, 失敗キー) を返す"""
    failed = []
    for item in schedule_select.today_items(schedule, now):
        key = item["key"]
        status = state_data.get(key, {}).get("status")
        if status in ("published", "prepared"):
            continue
        try:
            cid = client.create_container(
                user_id, token,
                video_url=item["video_url"],
                cover_url=item.get("cover_url"),
                caption=item["caption"],
                audio_id=item.get("audio_id"),
            )
            client.wait_for_container(token, cid)
        except client.ContainerError as e:
            print(f"[失敗] {key}: {e}", file=sys.stderr)
            failed.append(key)
            continue
        state_data = state_mod.mark_prepared(
            state_data, key, cid, datetime.datetime.now(JST).isoformat())
        print(f"[準備完了] {key} container_id={cid} 音源={item.get('audio_id')}")
    return state_data, failed


def main():
    token = os.environ["IG_ACCESS_TOKEN"]
    user_id = os.environ["IG_USER_ID"]

    days = ig_client.token_days_left(token)
    if days is not None:
        print(f"::notice::トークン残り {days} 日")
        if days < 14:
            print(f"::warning::トークンの残りが {days} 日。Business Suite の "
                  f"bizbot から再生成し、Secrets を更新すること")

    with open("schedule.json", encoding="utf-8") as f:
        schedule = json.load(f)
    now = datetime.datetime.now(JST)
    updated, failed = run(schedule, state_mod.load("state.json"),
                          now, user_id, token)
    state_mod.save("state.json", updated)
    if failed:
        print(f"::error::コンテナ作成に失敗: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
