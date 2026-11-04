"""Prueba del ajuste del drop al beat más cercano (caso drop entre dos beats)."""
from backend.audio import snap_to_nearest_beat


def test_snap_down():
    beats = [1.0, 2.0, 3.0]
    assert snap_to_nearest_beat(2.4, beats) == 2.0


def test_snap_up():
    beats = [1.0, 2.0, 3.0]
    assert snap_to_nearest_beat(2.6, beats) == 3.0


def test_snap_exact():
    beats = [1.0, 2.0, 3.0]
    assert snap_to_nearest_beat(2.0, beats) == 2.0


def test_snap_between_beats_no_equal():
    beats = [1.0, 1.5, 3.0]
    assert snap_to_nearest_beat(2.6, beats) == 3.0
    assert snap_to_nearest_beat(1.7, beats) == 1.5


def test_snap_empty_beats_returns_drop():
    assert snap_to_nearest_beat(1.5, []) == 1.5
