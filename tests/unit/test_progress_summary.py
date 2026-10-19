from __future__ import annotations

from datetime import UTC, datetime, timedelta

from serve.pages import _format_span, _progress_summary


def _row(done, total, *, seconds=60.0, phase="detecting"):
    started = datetime.now(UTC) - timedelta(seconds=seconds)
    return {
        "progress_phase": phase,
        "progress_done": done,
        "progress_total": total,
        "progress_started_at": started,
        "started_at": started,
    }


def test_eta_appears_from_the_very_first_completed_repo():
    summary = _progress_summary(_row(1, 100, seconds=120.0))
    assert summary["eta_seconds"] is not None
    assert summary["eta_provisional"] is True


def test_provisional_flag_clears_after_ten_repos():
    summary = _progress_summary(_row(12, 100))
    assert summary["eta_seconds"] is not None
    assert summary["eta_provisional"] is False


def test_no_eta_without_total_or_before_any_completion():
    assert _progress_summary(_row(0, 100))["eta"] is None
    assert _progress_summary(_row(5, None))["eta"] is None
    assert _progress_summary(_row(0, 100))["eta_provisional"] is False


def test_eta_provisional_value_is_phase_relative():
    summary = _progress_summary(_row(2, 102, seconds=100.0))
    assert 4000 <= summary["eta_seconds"] <= 6000


def test_eta_beyond_a_day_renders_in_days():
    assert _format_span(3 * 86400 + 5 * 3600) == "3d 5h"


def test_writing_stage_suppresses_the_eta():
    summary = _progress_summary(_row(50, 100, seconds=60.0, phase="writing"))
    assert summary["label"] == "Saving results"
    assert summary["eta"] is None
    assert summary["eta_seconds"] is None
    assert summary["eta_provisional"] is False
