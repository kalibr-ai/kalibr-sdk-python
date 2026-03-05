"""Voice routing example with Router.synthesize() and Router.transcribe().

Demonstrates:
- TTS routing across OpenAI and ElevenLabs
- STT routing across Whisper and Deepgram
- Cost tracking and outcome learning

Prerequisites:
    pip install kalibr[voice]
    export KALIBR_API_KEY=your-key
    export KALIBR_TENANT_ID=your-tenant-id
    export OPENAI_API_KEY=your-key
"""

from kalibr import Router

# --- TTS Routing ---
tts_router = Router(
    goal="text_to_speech",
    paths=["tts-1", "tts-1-hd"],
    success_when=lambda out: out is not None,
)

try:
    result = tts_router.synthesize(
        "Hello! This is a routed text-to-speech request.",
        voice="alloy",
    )
    print(f"TTS Result:")
    print(f"  Model: {result.model}")
    print(f"  Cost: ${result.cost_usd:.6f}")
    print(f"  Trace ID: {result.kalibr_trace_id}")
except Exception as e:
    print(f"TTS routing error (expected if no API key): {e}")

# --- STT Routing ---
stt_router = Router(
    goal="speech_to_text",
    paths=["whisper-1"],
)

try:
    # Note: requires an actual audio file
    # result = stt_router.transcribe(
    #     open("audio.mp3", "rb"),
    #     audio_duration_minutes=1.5,
    # )
    # print(f"STT Result: {result.text}")
    # print(f"  Cost: ${result.cost_usd:.6f}")
    print("STT Router: ready (provide an audio file to transcribe)")
except Exception as e:
    print(f"STT routing error: {e}")
