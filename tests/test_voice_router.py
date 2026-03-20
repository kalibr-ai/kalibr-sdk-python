"""Tests for Router voice methods (synthesize, transcribe)."""

import os
import pytest
from unittest.mock import patch, MagicMock

# Set required env vars before importing Router
os.environ.setdefault("KALIBR_API_KEY", "test-key")
os.environ.setdefault("KALIBR_TENANT_ID", "test-tenant")

from kalibr.router import Router


class TestRouterVoiceVendorDetection:
    def test_detect_openai_tts(self):
        router = Router(goal="test", paths=["tts-1"], auto_register=False)
        assert router._detect_voice_vendor("tts-1") == "openai"
        assert router._detect_voice_vendor("tts-1-hd") == "openai"

    def test_detect_openai_stt(self):
        router = Router(goal="test", paths=["whisper-1"], auto_register=False)
        assert router._detect_voice_vendor("whisper-1") == "openai"

    def test_detect_elevenlabs(self):
        router = Router(goal="test", paths=["eleven_multilingual_v2"], auto_register=False)
        assert router._detect_voice_vendor("eleven_multilingual_v2") == "elevenlabs"
        assert router._detect_voice_vendor("eleven_turbo_v2") == "elevenlabs"

    def test_detect_deepgram(self):
        router = Router(goal="test", paths=["nova-2"], auto_register=False)
        assert router._detect_voice_vendor("nova-2") == "deepgram"
        assert router._detect_voice_vendor("aura-asteria-en") == "deepgram"

    def test_detect_unknown_defaults_openai(self):
        router = Router(goal="test", paths=["unknown-voice"], auto_register=False)
        assert router._detect_voice_vendor("unknown-voice") == "openai"


class TestRouterSynthesize:
    @patch("kalibr.router.Router._call_openai_audio_tts")
    def test_synthesize_openai(self, mock_tts):
        mock_tts.return_value = b"audio-bytes"
        router = Router(goal="test_tts", paths=["tts-1"], auto_register=False)
        result = router.synthesize("Hello world", voice="alloy", model="tts-1")

        assert result.audio == b"audio-bytes"
        assert result.kalibr_trace_id is not None
        assert result.model == "tts-1"
        assert result.cost_usd > 0
        mock_tts.assert_called_once()

    @patch("kalibr.router.Router._call_elevenlabs")
    def test_synthesize_elevenlabs(self, mock_tts):
        mock_tts.return_value = b"el-audio"
        router = Router(
            goal="test_tts",
            paths=["eleven_multilingual_v2"],
            auto_register=False,
        )
        result = router.synthesize(
            "Hello world", voice="Rachel", model="eleven_multilingual_v2"
        )

        assert result.audio == b"el-audio"
        assert result.model == "eleven_multilingual_v2"
        assert result.cost_usd > 0
        mock_tts.assert_called_once()

    @patch("kalibr.router.Router._call_openai_audio_tts")
    def test_synthesize_cost_calculation(self, mock_tts):
        mock_tts.return_value = b"audio"
        router = Router(goal="test_tts", paths=["tts-1"], auto_register=False)
        text = "a" * 1000  # 1000 characters
        result = router.synthesize(text, model="tts-1")

        # TTS-1: 0.000015 per character
        expected_cost = 0.000015 * 1000
        assert abs(result.cost_usd - expected_cost) < 0.000001


class TestRouterTranscribe:
    @patch("kalibr.router.Router._call_openai_audio_stt")
    def test_transcribe_openai(self, mock_stt):
        mock_response = MagicMock()
        mock_response.text = "Hello world"
        mock_stt.return_value = mock_response
        router = Router(goal="test_stt", paths=["whisper-1"], auto_register=False)
        result = router.transcribe(
            b"audio-bytes", model="whisper-1", audio_duration_seconds=60.0
        )

        assert result.text == "Hello world"
        assert result.kalibr_trace_id is not None
        assert result.model == "whisper-1"
        mock_stt.assert_called_once()

    @patch("kalibr.router.Router._call_deepgram_stt")
    def test_transcribe_deepgram(self, mock_stt):
        mock_response = MagicMock()
        mock_response.text = "Transcribed text"
        mock_stt.return_value = mock_response
        router = Router(goal="test_stt", paths=["nova-2"], auto_register=False)
        result = router.transcribe(
            b"audio-bytes", model="nova-2", audio_duration_seconds=300.0
        )

        assert result.model == "nova-2"
        assert result.kalibr_trace_id is not None
        mock_stt.assert_called_once()

    @patch("kalibr.router.Router._call_openai_audio_stt")
    def test_transcribe_cost_with_duration(self, mock_stt):
        mock_stt.return_value = "Hello"
        router = Router(goal="test_stt", paths=["whisper-1"], auto_register=False)
        result = router.transcribe(
            b"audio", model="whisper-1", audio_duration_seconds=600.0
        )

        # Whisper-1: 0.0001 per second, 600 seconds
        expected_cost = 0.0001 * 600
        assert abs(result.cost_usd - expected_cost) < 0.000001


class TestRouterVoiceDispatch:
    @patch("kalibr.router.Router._call_openai_audio_tts")
    def test_dispatch_tts_openai(self, mock_tts):
        mock_tts.return_value = b"audio"
        router = Router(goal="test", paths=["tts-1"], auto_register=False)
        router._dispatch_voice_tts("tts-1", "text", "alloy")
        mock_tts.assert_called_once()

    @patch("kalibr.router.Router._call_elevenlabs")
    def test_dispatch_tts_elevenlabs(self, mock_tts):
        mock_tts.return_value = b"audio"
        router = Router(goal="test", paths=["eleven_multilingual_v2"], auto_register=False)
        router._dispatch_voice_tts("eleven_multilingual_v2", "text", "Rachel")
        mock_tts.assert_called_once()

    @patch("kalibr.router.Router._call_openai_audio_stt")
    def test_dispatch_stt_openai(self, mock_stt):
        mock_stt.return_value = "text"
        router = Router(goal="test", paths=["whisper-1"], auto_register=False)
        router._dispatch_voice_stt("whisper-1", b"audio")
        mock_stt.assert_called_once()

    @patch("kalibr.router.Router._call_deepgram_stt")
    def test_dispatch_stt_deepgram(self, mock_stt):
        mock_stt.return_value = "text"
        router = Router(goal="test", paths=["nova-2"], auto_register=False)
        router._dispatch_voice_stt("nova-2", b"audio")
        mock_stt.assert_called_once()
