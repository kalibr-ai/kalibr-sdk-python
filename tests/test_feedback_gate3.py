"""Tests for Gate 3 delta tracking, momentum, and silence reward handler."""

import json
import pathlib
import time
from unittest.mock import patch, MagicMock

import pytest

from kalibr.feedback import (
    _bag_of_words_cosine,
    _compute_delta,
    _compute_momentum,
    report_session_end,
    _read_session,
    _get_session_path,
)


class TestComputeDelta:
    def test_compute_delta_basic(self):
        delta = _compute_delta("hello world", "hello there world")
        assert "cosine" in delta
        assert "len_ratio" in delta
        assert "frust" in delta
        assert "affirm" in delta
        assert 0.0 <= delta["cosine"] <= 1.0
        assert delta["len_ratio"] > 0
        assert isinstance(delta["frust"], int)
        assert isinstance(delta["affirm"], int)

    def test_compute_delta_frustration(self):
        delta = _compute_delta("do this", "wrong again fix this")
        assert delta["frust"] >= 2  # "wrong", "again", "fix"

    def test_compute_delta_affirmation(self):
        delta = _compute_delta("do this", "thanks perfect great")
        assert delta["affirm"] >= 3


class TestComputeMomentum:
    def test_compute_momentum_closing(self):
        # High cosine, short messages, no frustration, some affirmation
        deltas = [
            {"cosine": 0.8, "len_ratio": 0.9, "frust": 0, "affirm": 1},
            {"cosine": 0.75, "len_ratio": 1.0, "frust": 0, "affirm": 1},
            {"cosine": 0.85, "len_ratio": 0.8, "frust": 0, "affirm": 2},
        ]
        assert _compute_momentum(deltas) == "closing"

    def test_compute_momentum_widening(self):
        # Low cosine, frustrated messages
        deltas = [
            {"cosine": 0.3, "len_ratio": 1.5, "frust": 2, "affirm": 0},
            {"cosine": 0.4, "len_ratio": 1.4, "frust": 1, "affirm": 0},
        ]
        assert _compute_momentum(deltas) == "widening"

    def test_compute_momentum_flat_insufficient_deltas(self):
        assert _compute_momentum([]) == "flat"
        assert _compute_momentum([{"cosine": 0.5, "len_ratio": 1.0, "frust": 0, "affirm": 0}]) == "flat"

    def test_compute_momentum_flat_no_clear_signal(self):
        deltas = [
            {"cosine": 0.6, "len_ratio": 1.1, "frust": 0, "affirm": 0},
            {"cosine": 0.65, "len_ratio": 1.0, "frust": 0, "affirm": 0},
        ]
        assert _compute_momentum(deltas) == "flat"


class TestReportSessionEnd:
    def _write_session(self, tmp_path, session_id, deltas, momentum="flat"):
        session_dir = tmp_path / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_data = {
            "trace_id": "test-trace-123",
            "goal": "test-goal",
            "ts": time.time(),
            "deltas": deltas,
            "momentum": momentum,
            "last_user_message": "hello",
        }
        path = session_dir / f"{session_id}.json"
        path.write_text(json.dumps(session_data))
        return path

    @patch("kalibr.feedback.emit_signal")
    @patch("kalibr.feedback._get_session_path")
    def test_report_session_end_no_signal_on_flat(self, mock_path, mock_emit, tmp_path):
        path = self._write_session(tmp_path, "sess1", [
            {"cosine": 0.6, "len_ratio": 1.0, "frust": 0, "affirm": 0},
            {"cosine": 0.62, "len_ratio": 1.05, "frust": 0, "affirm": 0},
        ])
        mock_path.return_value = path
        report_session_end("sess1")
        mock_emit.assert_not_called()

    @patch("kalibr.feedback.emit_signal")
    @patch("kalibr.feedback._get_session_path")
    def test_report_session_end_closing_emits_positive(self, mock_path, mock_emit, tmp_path):
        path = self._write_session(tmp_path, "sess2", [
            {"cosine": 0.8, "len_ratio": 0.9, "frust": 0, "affirm": 1},
            {"cosine": 0.75, "len_ratio": 1.0, "frust": 0, "affirm": 1},
            {"cosine": 0.85, "len_ratio": 0.8, "frust": 0, "affirm": 2},
        ])
        mock_path.return_value = path
        report_session_end("sess2")
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["signal_type"] == "user_accepted"
        assert call_kwargs["strength"] == 0.65
        assert call_kwargs["confidence"] == 0.4

    @patch("kalibr.feedback.emit_signal")
    @patch("kalibr.feedback._get_session_path")
    def test_report_session_end_widening_emits_negative(self, mock_path, mock_emit, tmp_path):
        path = self._write_session(tmp_path, "sess3", [
            {"cosine": 0.3, "len_ratio": 1.5, "frust": 2, "affirm": 0},
            {"cosine": 0.4, "len_ratio": 1.4, "frust": 1, "affirm": 0},
        ])
        mock_path.return_value = path
        report_session_end("sess3")
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["signal_type"] == "user_rejected"
        assert call_kwargs["strength"] == 0.25
        assert call_kwargs["confidence"] == 0.4

    @patch("kalibr.feedback.emit_signal")
    @patch("kalibr.feedback._get_session_path")
    def test_report_session_end_requires_2_deltas(self, mock_path, mock_emit, tmp_path):
        path = self._write_session(tmp_path, "sess4", [
            {"cosine": 0.3, "len_ratio": 1.5, "frust": 2, "affirm": 0},
        ])
        mock_path.return_value = path
        report_session_end("sess4")
        mock_emit.assert_not_called()
