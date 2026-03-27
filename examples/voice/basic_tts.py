"""Basic TTS example with auto-instrumentation.

Demonstrates:
- ElevenLabs TTS with automatic tracing
- OpenAI TTS with automatic tracing
- Cost tracking for voice operations

Prerequisites:
    pip install kalibr[voice]
    export KALIBR_API_KEY=your-key
    export KALIBR_TENANT_ID=your-tenant-id
    export OPENAI_API_KEY=your-key
    export ELEVENLABS_API_KEY=your-key
"""

from kalibr import auto_instrument

# Instrument both text LLMs and voice SDKs
auto_instrument(["openai", "elevenlabs"])

# --- OpenAI TTS ---
try:
    from openai import OpenAI

    client = OpenAI()
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input="Hello! This is a test of OpenAI text-to-speech with Kalibr tracing.",
    )
    print(f"OpenAI TTS: generated {len(response.content)} bytes of audio")
except ImportError:
    print("OpenAI SDK not installed, skipping OpenAI TTS example")
except Exception as e:
    print(f"OpenAI TTS error (expected if no API key): {e}")

# --- ElevenLabs TTS ---
try:
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs()
    audio = client.generate(
        text="Hello! This is a test of ElevenLabs text-to-speech with Kalibr tracing.",
        voice="Rachel",
        model="eleven_multilingual_v2",
    )
    print("ElevenLabs TTS: audio generated successfully")
except ImportError:
    print("ElevenLabs SDK not installed, skipping ElevenLabs TTS example")
except Exception as e:
    print(f"ElevenLabs TTS error (expected if no API key): {e}")

print("\nCheck /tmp/kalibr_otel_spans.jsonl for traced voice spans")
