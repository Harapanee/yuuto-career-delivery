# -*- coding: utf-8 -*-
"""投稿済み記録。二重投稿の防止が唯一かつ最大の目的。"""
import datetime
import json
import os
import uuid


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(path, data):
    """state.json を壊さないよう、同一ディレクトリに一時ファイルを書いてから
    os.replace() で置き換える(同一ファイルシステム上でアトミック)。
    書き込み中にプロセスが落ちても、元のファイルはそのまま残る。
    このファイルは二重投稿を防ぐ唯一の記録なので、破損は許容できない。
    """
    directory = os.path.dirname(path) or "."
    tmp_path = os.path.join(directory, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def is_published(data, key):
    return data.get(key, {}).get("status") == "published"


def mark_prepared(data, key, container_id, at_iso):
    out = dict(data)
    entry = dict(out.get(key, {}))
    entry.update({"status": "prepared", "container_id": container_id,
                  "container_created_at": at_iso})
    out[key] = entry
    return out


def mark_published(data, key, media_id, at_iso):
    out = dict(data)
    entry = dict(out.get(key, {}))
    entry.update({"status": "published", "media_id": media_id,
                  "published_at": at_iso})
    out[key] = entry
    return out


def fresh_container_id(data, key, now, max_age_hours=23):
    """まだ使えるコンテナIDを返す。無い/古い場合は None(呼び出し側で作り直す)"""
    entry = data.get(key, {})
    cid = entry.get("container_id")
    created = entry.get("container_created_at")
    if not cid or not created:
        return None
    age = now - datetime.datetime.fromisoformat(created)
    return cid if age < datetime.timedelta(hours=max_age_hours) else None
