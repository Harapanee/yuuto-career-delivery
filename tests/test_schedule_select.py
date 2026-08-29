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


def test_select_for_now_90分を超えたら選ばない():
    now = datetime.datetime(2026, 9, 1, 7, 31, tzinfo=JST)
    assert schedule_select.select_for_now(SCHEDULE, now) is None


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
