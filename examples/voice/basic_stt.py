"""Basic STT example with auto-instrumentation.

Demonstrates:
- Deepgram STT with automatic tracing
- OpenAI Whisper STT with automatic tracing
- Cost tracking for transcription operations

Prerequisites:
    pip install kalibr[voice]
    export KALIBR_API_KEY=your-key
    export KALIBR_TENANT_ID=your-tenant-id
    export OPENAI_API_KEY=your-key
    export DEEPGRAM_API_KEY=your-key
"""

from kalibr import auto_instrument

# Instrument both text LLMs and voice SDKs
auto_instrument(["openai", "deepgram"])

# --- OpenAI Whisper STT ---
try:
    from openai import OpenAI

    client = OpenAI()
    # Note: requires an actual audio file
    # transcript = client.audio.transcriptions.create(
    #     model="whisper-1",
    #     file=open("audio.mp3", "rb"),
    # )
    # print(f"Whisper STT: {transcript.text}")
    print("OpenAI Whisper STT: ready (provide an audio file to transcribe)")
except ImportError:
    print("OpenAI SDK not installed, skipping Whisper STT example")

# --- Deepgram STT ---
try:
    from deepgram import DeepgramClient, PrerecordedOptions

    client = DeepgramClient()
    # Note: requires an actual audio file or URL
    # options = PrerecordedOptions(model="nova-2")
    # result = client.listen.rest.v("1").transcribe_url(
    #     {"url": "https://example.com/audio.mp3"},
    #     options,
    # )
    # print(f"Deepgram STT: {result.results.channels[0].alternatives[0].transcript}")
    print("Deepgram STT: ready (provide an audio file to transcribe)")
except ImportError:
    print("Deepgram SDK not installed, skipping Deepgram STT example")

print("\nCheck /tmp/kalibr_otel_spans.jsonl for traced voice spans")
