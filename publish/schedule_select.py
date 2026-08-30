# -*- coding: utf-8 -*-
"""現在時刻から対象エントリを選ぶ。

GitHub Actions の cron は数分〜30分どころか、数時間遅れる回がある。
2026-08-30 の 06:00 枠は cron が4発とも発火したが全て約2時間遅れ、
当時の ±90分 判定を外れて全てスキップされ、**投稿されないまま終わった**。
遅れて届いた投稿をこちら側で捨てていたことになる。

そこで窓を ±3時間 に広げた。投稿枠の間隔(しゅうと 6時間 / ゆうと 7時間)より
狭いので、隣の枠を誤って拾うことはない。
それを超えて離れているものは取りこぼしとみなし、自動では投稿しない
(その場合は workflow_dispatch の key 指定で手動公開する)。

**時刻の正確さより「投稿されること」を優先している。**最大3時間ずれる。
時間帯の効果を検証したくなったら、ここを戻すのではなく常時起動の環境に移すこと。
"""
import datetime


def _at(item):
    return datetime.datetime.fromisoformat(item["publish_at"])


def select_for_now(schedule, now, early_minutes=35, late_minutes=180):
    """現在時刻に最も近いエントリを1件返す。範囲外なら None

    **前と後ろで許容幅が違う。**cron の遅延は後ろにしか起きないため:
      ・後ろ(遅れ)は 180分 まで許す … 2時間遅れても投稿を落とさないため
      ・前(前倒し)は 35分 だけ許す … cron を :41(19分前)に置いている分 + 余裕

    前後を同じ180分にすると、6時枠を落とした日の9時半の起動が
    **12時の動画を2時間半早く出してしまう。**そのための非対称。
    """
    early = datetime.timedelta(minutes=early_minutes)
    late = datetime.timedelta(minutes=late_minutes)
    candidates = [x for x in schedule["items"] if -early <= now - _at(x) <= late]
    if not candidates:
        return None
    return min(candidates, key=lambda x: abs(_at(x) - now))


def today_items(schedule, now):
    """now と同じ日(JST)のエントリをすべて返す"""
    return [x for x in schedule["items"] if _at(x).date() == now.date()]
