# -*- coding: utf-8 -*-
"""cron の冗長化が将来こっそり1発に戻らないよう固定する。

GitHub の定時実行は遅延するだけでなく丸ごと発火しない回がある(2026-08-29 実例)。
1発勝負に戻すと投稿が落ちるが、落ちても CI は緑のままなので気づけない。
"""
import datetime
import json
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
JST = datetime.timezone(datetime.timedelta(hours=9))
WINDOW = datetime.timedelta(minutes=180)  # publish.py の判定窓と同じ


def _crons(name):
    d = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    return [c["cron"] for c in d[True]["schedule"]]   # PyYAML は on: を True と読む


def _jst(cron):
    m, h = cron.split()[0], cron.split()[1]
    u = datetime.datetime(2026, 1, 1, int(h), int(m), tzinfo=datetime.timezone.utc)
    return u.astimezone(JST).time()


def test_公開cronは枠ごとに4発ある():
    got = sorted(_jst(c) for c in _crons("publish.yml"))
    assert len(got) == 8, f"1枠4発 × 2枠 = 8発のはず: {got}"
    for slot in (datetime.time(12, 0), datetime.time(19, 0)):
        near = [t for t in got if abs(
            datetime.datetime.combine(datetime.date(2026, 1, 1), t)
            - datetime.datetime.combine(datetime.date(2026, 1, 1), slot)) <= WINDOW]
        assert len(near) == 4, f"{slot} 枠の発火が {len(near)} 発しかない"


def test_公開cronは全て予定時刻の判定窓内に入る():
    """窓の外に置くと publish.py がスキップして永久に投稿されない。"""
    slots = [datetime.time(12, 0), datetime.time(19, 0)]
    for c in _crons("publish.yml"):
        t = _jst(c)
        d = min(abs(datetime.datetime.combine(datetime.date(2026, 1, 1), t)
                    - datetime.datetime.combine(datetime.date(2026, 1, 1), s)) for s in slots)
        assert d <= WINDOW, f"{c} ({t}) はどの枠からも判定窓の外"


def test_事前作成は0時と公開前の保険の2発ある():
    got = sorted(_jst(c) for c in _crons("prepare.yml"))
    assert len(got) == 2, f"0時 + 保険の2発のはず: {got}"
    assert got[0] == datetime.time(0, 0), "0時の本命が無い(日付が前日にずれる)"
    assert datetime.time(11, 0) < got[1] < datetime.time(12, 0), \
        "保険は最初の公開(12:00)より前に置くこと"


def test_公開ジョブは公開前にstateを取り直す():
    """checkout は起動時点の SHA を取る。cron が遅延して2発が同時に作られると
    後発が古い state.json で起動して二重投稿する。その手当てが消えていないか。"""
    y = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "git fetch" in y and "state.json" in y, "state.json の取り直しが消えている"
    steps = yaml.safe_load(y)["jobs"]["publish"]["steps"]
    names = [s.get("name", s.get("uses", "")) for s in steps]
    fetch = next(i for i, n in enumerate(names) if "origin の最新" in n)
    pub = next(i for i, n in enumerate(names) if "公開する" in n)
    assert fetch < pub, "取り直しが公開より後になっている"


def test_公開cronはscheduleの投稿枠と一致する():
    """schedule.json の時刻を変えたら cron も直す必要がある。"""
    items = json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))["items"]
    slots = {datetime.datetime.fromisoformat(i["publish_at"]).time() for i in items}
    covered = {_jst(c) for c in _crons("publish.yml")}
    for s in slots:
        near = [t for t in covered if abs(
            datetime.datetime.combine(datetime.date(2026, 1, 1), t)
            - datetime.datetime.combine(datetime.date(2026, 1, 1), s)) <= WINDOW]
        assert near, f"schedule.json に {s} の枠があるのに cron が無い"
