# -*- coding: utf-8 -*-
"""公開フェーズ: 6/12/18時に media_publish を撃つ。

正常時は事前作成済みのコンテナを公開するだけなので1〜2秒で終わる。
コンテナが無い、または24時間の有効期限に近い場合はその場で作り直す。
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


def run(schedule, state_data, now, user_id, token, *, client=ig_client, force_key=None):
    """対象1件を公開する。(更新後state, 公開したキー or None) を返す

    force_key を渡すと ±90分の窓を無視してそのキーを公開する(取りこぼしの手動復旧用)。
    **窓だけを外し、「公開済みならスキップ」は外さない。**ここまで外すと二重投稿する。
    """
    if force_key:
        item = next((x for x in schedule["items"] if x["key"] == force_key), None)
        if item is None:
            print(f"::error::{force_key} が schedule.json に無い")
            return state_data, None
        print(f"[手動] {force_key} を時刻の窓を無視して公開する")
    else:
        item = schedule_select.select_for_now(schedule, now)
    if item is None:
        print("[スキップ] 予定時刻から離れているため何もしない")
        return state_data, None


    key = item["key"]
    if state_mod.is_published(state_data, key):
        print(f"[スキップ] {key} は公開済み")
        return state_data, None

    cid = state_mod.fresh_container_id(state_data, key, now)
    if cid is None:
        print(f"[作り直し] {key} のコンテナを作成する")
        cid = client.create_container(
            user_id, token,
            video_url=item["video_url"],
            cover_url=item.get("cover_url"),
            caption=item["caption"],
            audio_id=item.get("audio_id"),
        )
        client.wait_for_container(token, cid)

    media_id = client.publish_container(user_id, token, cid)
    state_data = state_mod.mark_published(
        state_data, key, media_id, datetime.datetime.now(JST).isoformat())
    print(f"[公開] {key} media_id={media_id}")
    return state_data, key


def main():
    token = os.environ["IG_ACCESS_TOKEN"]
    user_id = os.environ["IG_USER_ID"]
    with open("schedule.json", encoding="utf-8") as f:
        schedule = json.load(f)
    now = datetime.datetime.now(JST)
    force_key = os.environ.get("PUBLISH_KEY") or None
    try:
        updated, key = run(schedule, state_mod.load("state.json"),
                           now, user_id, token, force_key=force_key)
    except ig_client.ContainerError as e:
        print(f"::error::公開に失敗: {e}")
        sys.exit(1)
    if key:
        state_mod.save("state.json", updated)


if __name__ == "__main__":
    main()
