"""Prueba del número de imágenes necesarias como ceil(beats_tras_drop / n)."""
import math

from backend.render import compute_timeline


def count_after(beats, drop, duration):
    return len([b for b in beats if drop < b <= duration])


def test_image_count_matches_formula():
    beats = [float(i) for i in range(1, 11)]  # 10 beats (1..10)
    drop = 0.0
    duration = 12.0
    for n in (1, 2, 4):
        _, num = compute_timeline(beats, drop, n, duration)
        assert num == math.ceil(count_after(beats, drop, duration) / n)


def test_partial_group_is_one_image():
    # 10 beats tras drop, n=4 -> ceil(10/4) = 3 imágenes
    beats = [float(i) for i in range(1, 11)]
    intervals, num = compute_timeline(beats, 0.0, 4, 12.0)
    assert num == 3
    assert len(intervals) == 3
    assert intervals[-1][1] == 12.0  # última imagen hasta el final


def test_drop_between_beats():
    # drop entre dos beats: cuenta solo los beats posteriores estrictos
    beats = [1.0, 2.0, 3.0, 4.0, 5.0]
    drop = 2.3  # entre 2.0 y 3.0
    duration = 6.0
    after = count_after(beats, drop, duration)  # 3.0,4.0,5.0 -> 3
    _, num = compute_timeline(beats, drop, 1, duration)
    assert num == math.ceil(after / 1) == 3


def test_no_beats_after_drop():
    beats = [1.0, 2.0]
    drop = 2.5
    intervals, num = compute_timeline(beats, drop, 1, 4.0)
    # sin beats tras el drop: una sola imagen hasta el final
    assert num == 1
    assert intervals == [(2.5, 4.0)]
