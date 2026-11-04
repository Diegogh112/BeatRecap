"""Pruebas del cálculo de intervalos de beats (img_starts/img_ends)."""
import math

from backend.render import compute_timeline


def beats_after(beats, drop, duration):
    return [b for b in beats if drop < b <= duration]


def test_first_interval_starts_at_drop():
    beats = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    drop = 0.5
    duration = 6.0
    intervals, num = compute_timeline(beats, drop, 1, duration)
    assert intervals[0][0] == drop, "el primer intervalo debe empezar en el drop"
    assert intervals[-1][1] == duration, "el último intervalo se extiende a duration"
    assert num == math.ceil(len(beats_after(beats, drop, duration)) / 1)


def test_no_gap_intro_to_carousel():
    # la intro termina en el drop y el carrusel empieza en el drop: sin huecos
    beats = [1.0, 2.0, 3.0, 4.0, 5.0]
    drop = 2.0
    intervals, _ = compute_timeline(beats, drop, 1, 6.0)
    # el último beat antes del drop es 1.0; el primer intervalo empieza en 2.0
    assert intervals[0][0] == 2.0


def test_intervals_contiguous():
    beats = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    drop = 1.0
    intervals, _ = compute_timeline(beats, drop, 1, 7.0)
    for i in range(len(intervals) - 1):
        assert intervals[i][1] == intervals[i + 1][0], "los intervalos son contiguos"


def test_change_every_n_beats():
    beats = [float(i) for i in range(1, 11)]  # 1..10
    drop = 0.0
    duration = 12.0
    for n in (1, 2, 4):
        intervals, num = compute_timeline(beats, drop, n, duration)
        after = beats_after(beats, drop, duration)
        assert num == math.ceil(len(after) / n)
        assert intervals[0][0] == drop
        assert intervals[-1][1] == duration
        assert len(intervals) == num


def test_change_points_are_every_n_beat():
    beats = [float(i) for i in range(1, 11)]  # 1..10
    drop = 0.0
    duration = 12.0
    n = 2
    intervals, _ = compute_timeline(beats, drop, n, duration)
    # con n=2 y 10 beats -> 5 imágenes; cambios en beats[1], beats[3], beats[5], beats[7]
    # img_starts = [0, 2, 4, 6, 8]
    starts = [iv[0] for iv in intervals]
    assert starts == [0.0, 2.0, 4.0, 6.0, 8.0]
