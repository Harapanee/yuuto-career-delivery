# -*- coding: utf-8 -*-
"""現在時刻から対象エントリを選ぶ。

GitHub Actions の cron は数分〜30分遅延する。定時ちょうどに起動しない前提で、
予定時刻から ±90分 の範囲にあるものを対象とする。
それを超えて離れているものは取りこぼしとみなし、自動では投稿しない。
"""
import datetime


def _at(item):
    return datetime.datetime.fromisoformat(item["publish_at"])


def select_for_now(schedule, now, window_minutes=90):
    """現在時刻に最も近いエントリを1件返す。範囲外なら None"""
    window = datetime.timedelta(minutes=window_minutes)
    candidates = [x for x in schedule["items"] if abs(_at(x) - now) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda x: abs(_at(x) - now))


def today_items(schedule, now):
    """now と同じ日(JST)のエントリをすべて返す"""
    return [x for x in schedule["items"] if _at(x).date() == now.date()]
