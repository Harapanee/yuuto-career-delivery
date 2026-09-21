# -*- coding: utf-8 -*-
"""Threads 公開フェーズ: 7:00 / 12:30 / 21:00 に1本出す。

IG と違いコンテナは数秒で FINISHED になるので事前作成フェーズは無い。
作成→待機→公開→(reply_text があれば自己リプ)を一気にやる。
自己リプの失敗は本体の公開を巻き戻せないので、警告を出して published のまま記録する。
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

import schedule_select
import state as state_mod
import threads_client

JST = ZoneInfo("Asia/Tokyo")
SCHEDULE_PATH = "threads_schedule.json"
STATE_PATH = "threads_state.json"


def _publish(client, user_id, token, **kw):
    cid = client.create_container(user_id, token, **kw)
    client.wait_for_container(token, cid)
    return client.publish_container(user_id, token, cid)


def run(schedule, state_data, now, user_id, token, *, client=threads_client,
        force_key=None):
    """対象1件を公開する。(更新後state, 公開したキー or None) を返す。
    force_key は時刻の窓だけを外す。「公開済みならスキップ」は外さない"""
    if force_key:
        item = next((x for x in schedule["items"] if x["key"] == force_key), None)
        if item is None:
            print(f"::error::{force_key} が {SCHEDULE_PATH} に無い")
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

    post_id = _publish(client, user_id, token,
                       text=item["text"], image_url=item.get("image_url"))
    at = datetime.datetime.now(JST).isoformat()
    out = dict(state_data)
    out[key] = {"status": "published", "post_id": post_id, "published_at": at}
    print(f"[公開] {key} post_id={post_id}")

    reply_text = item.get("reply_text")
    if reply_text:
        try:
            reply_id = _publish(client, user_id, token,
                                text=reply_text, reply_to_id=post_id)
            out[key]["reply_id"] = reply_id
            print(f"[自己リプ] {key} reply_id={reply_id}")
        except client.ContainerError as e:
            out[key]["reply_error"] = str(e)
            print(f"::warning::{key} の自己リプに失敗(本体は公開済み): {e}")
    return out, key


def main():
    token = os.environ["THREADS_ACCESS_TOKEN"]
    user_id = os.environ["THREADS_USER_ID"]
    with open(SCHEDULE_PATH, encoding="utf-8") as f:
        schedule = json.load(f)
    now = datetime.datetime.now(JST)
    force_key = os.environ.get("PUBLISH_KEY") or None
    try:
        updated, key = run(schedule, state_mod.load(STATE_PATH),
                           now, user_id, token, force_key=force_key)
    except threads_client.ContainerError as e:
        print(f"::error::公開に失敗: {e}")
        sys.exit(1)
    if key:
        state_mod.save(STATE_PATH, updated)


if __name__ == "__main__":
    main()
