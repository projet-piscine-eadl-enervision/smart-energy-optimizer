"""Épisodes de panne de capteur et signal de vivacité du collecteur."""
import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from mock_client.schemas.sensor import SiteSensors
from pipeline import heartbeat
from pipeline.sensors import Episode, plan_changes

NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)


def site(**sensors) -> SiteSensors:
    payload = {name: {"status": "ok", "failing_until": None} for name in ("consumption", "electrical")}
    payload.update(sensors)
    return SiteSensors(site_id="SITE001", site_name="x", overall="degraded", sensors=payload)


def failing(until):
    return {"status": "failing", "failing_until": until}


def test_new_failure_opens_an_episode_at_the_time_it_is_seen():
    opened, updated = plan_changes([site(consumption=failing(NOW + timedelta(seconds=40)))], {}, NOW)

    assert updated == []
    assert opened == [
        {"site_id": "SITE001", "sensor": "consumption", "started_at": NOW, "failing_until": NOW + timedelta(seconds=40)}
    ]


def test_a_failure_still_in_progress_opens_nothing():
    until = NOW + timedelta(seconds=30)
    latest = {("SITE001", "consumption"): Episode(NOW - timedelta(seconds=20), until)}

    assert plan_changes([site(consumption=failing(until))], latest, NOW) == ([], [])


def test_announced_end_that_moves_updates_the_same_episode():
    started = NOW - timedelta(seconds=20)
    latest = {("SITE001", "consumption"): Episode(started, NOW + timedelta(seconds=10))}

    opened, updated = plan_changes([site(consumption=failing(NOW + timedelta(seconds=45)))], latest, NOW)

    assert opened == []
    assert updated[0]["started_at"] == started and updated[0]["failing_until"] == NOW + timedelta(seconds=45)


def test_failure_after_the_previous_one_ended_is_a_new_episode():
    latest = {("SITE001", "consumption"): Episode(NOW - timedelta(minutes=5), NOW - timedelta(minutes=4))}

    opened, updated = plan_changes([site(consumption=failing(NOW + timedelta(seconds=40)))], latest, NOW)

    assert len(opened) == 1 and opened[0]["started_at"] == NOW and updated == []


def test_open_ended_episode_is_closed_when_the_sensor_is_ok_again():
    started = NOW - timedelta(minutes=2)
    latest = {("SITE001", "consumption"): Episode(started, None)}

    opened, updated = plan_changes([site()], latest, NOW)

    assert opened == [] and updated == [
        {"site_id": "SITE001", "sensor": "consumption", "started_at": started, "failing_until": NOW}
    ]


def test_unknown_sensor_names_are_ignored():
    assert plan_changes([site(flux_capacitor=failing(NOW))], {}, NOW) == ([], [])


@pytest.fixture
def beat_file(tmp_path, monkeypatch):
    path = tmp_path / "beat"
    monkeypatch.setenv("HEARTBEAT_FILE", str(path))
    return path


def test_no_heartbeat_yet_is_unhealthy(beat_file, capsys):
    assert heartbeat.age() is None
    assert heartbeat.main([]) == 1
    assert "no successful tour" in capsys.readouterr().out


def test_recent_heartbeat_is_healthy_and_old_one_is_not(beat_file, monkeypatch):
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "60")
    heartbeat.beat()
    assert heartbeat.main([]) == 0

    old = time.time() - 181
    os.utime(beat_file, (old, old))
    beat_file.write_text(str(old))
    assert heartbeat.main([]) == 1
    assert heartbeat.main(["--max-age", "300"]) == 0


def test_garbage_in_the_heartbeat_file_is_unhealthy(beat_file):
    beat_file.write_text("pas un nombre")
    assert heartbeat.age() is None
