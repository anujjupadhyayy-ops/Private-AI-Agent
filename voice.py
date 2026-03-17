import whisper, sounddevice, scipy.io.wavfile, tempfile, numpy as np

# Load the Whisper model — 'base' is fast on Apple Silicon
# Options: tiny, base, small, medium (bigger = more accurate but slower)
model = whisper.load_model("base")

def record_and_transcribe(duration: int = 5) -> str:
    """Record audio from mic for `duration` seconds and transcribe it."""
    sample_rate = 16000
    print(f"Recording for {duration} seconds...")
    audio = sounddevice.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32'
    )
    sounddevice.wait()  # wait until recording is complete

    # Save to temp file and transcribe
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        scipy.io.wavfile.write(f.name, sample_rate, audio)
        result = model.transcribe(f.name)
        return result["text"].strip()