import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publish"))
from zoneinfo import ZoneInfo
import schedule_select

JST = ZoneInfo("Asia/Tokyo")
SCHEDULE = {"items": [
    {"key": "day01_0600", "publish_at": "2026-09-01T06:00:00+09:00"},
    {"key": "day01_1200", "publish_at": "2026-09-01T12:00:00+09:00"},
    {"key": "day01_1800", "publish_at": "2026-09-01T18:00:00+09:00"},
    {"key": "day02_0600", "publish_at": "2026-09-02T06:00:00+09:00"},
]}


def test_select_for_now_定時ちょうど():
    now = datetime.datetime(2026, 9, 1, 6, 0, tzinfo=JST)
    assert schedule_select.select_for_now(SCHEDULE, now)["key"] == "day01_0600"


def test_select_for_now_25分遅れでも選ぶ():
    now = datetime.datetime(2026, 9, 1, 6, 25, tzinfo=JST)
    assert schedule_select.select_for_now(SCHEDULE, now)["key"] == "day01_0600"


def test_select_for_now_2時間遅れでも選ぶ():
    """2026-08-30 に cron が約2時間遅れて全て捨てられた。窓を180分にした理由。"""
    now = datetime.datetime(2026, 9, 1, 8, 0, tzinfo=JST)
    assert schedule_select.select_for_now(SCHEDULE, now)["key"] == "day01_0600"


def test_select_for_now_判定窓を超えて遅れたら選ばない():
    now = datetime.datetime(2026, 9, 1, 9, 1, tzinfo=JST)   # 06:00 から181分
    assert schedule_select.select_for_now(SCHEDULE, now) is None


def test_select_for_now_次の枠を大きく前倒ししない():
    """遅延は後ろにしか起きない。前倒しを広く許すと次の動画が早く出てしまう。"""
    now = datetime.datetime(2026, 9, 1, 9, 30, tzinfo=JST)  # 12:00 の2時間半前
    assert schedule_select.select_for_now(SCHEDULE, now) is None


def test_select_for_now_cronの前倒し分は許す():
    now = datetime.datetime(2026, 9, 1, 5, 41, tzinfo=JST)  # 06:00 の19分前
    assert schedule_select.select_for_now(SCHEDULE, now)["key"] == "day01_0600"


def test_select_for_now_最も近いものを選ぶ():
    now = datetime.datetime(2026, 9, 1, 11, 30, tzinfo=JST)
    assert schedule_select.select_for_now(SCHEDULE, now)["key"] == "day01_1200"


def test_today_items_その日の3本を返す():
    now = datetime.datetime(2026, 9, 1, 0, 5, tzinfo=JST)
    got = [x["key"] for x in schedule_select.today_items(SCHEDULE, now)]
    assert got == ["day01_0600", "day01_1200", "day01_1800"]


def test_today_items_該当なしなら空():
    now = datetime.datetime(2026, 12, 1, 0, 5, tzinfo=JST)
    assert schedule_select.today_items(SCHEDULE, now) == []
