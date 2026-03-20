import whisper, sounddevice, scipy.io.wavfile, tempfile, numpy as np
# whisper      — OpenAI's speech-to-text model, runs entirely locally
# sounddevice  — records audio from your Mac's microphone
# scipy.io.wavfile — saves recorded audio to a WAV file format
# tempfile     — creates temporary files that clean themselves up
# numpy        — numerical array handling, required by sounddevice for audio data

model = whisper.load_model("base")
# Loads the Whisper "base" model into memory at startup
# This happens once when voice.py is imported — not on every transcription
# "base" = 74MB model, fast on Apple Silicon, good enough for clear speech
# Alternatives: "tiny" (faster, less accurate), "small"/"medium" (slower, more accurate)
# The model runs 100% locally — your voice never leaves your Mac

def record_and_transcribe(duration: int = 5) -> str:
    """Record audio from mic for `duration` seconds and transcribe it."""
    
    sample_rate = 16000
    # 16,000 Hz (16kHz) — the sample rate Whisper was trained on
    # Using a different rate would require resampling — 16kHz is the correct default
    # Higher sample rates capture more audio detail but Whisper doesn't need more than 16kHz
    
    print(f"Recording for {duration} seconds...")
    
    audio = sounddevice.rec(
        int(duration * sample_rate),
        # Total number of samples to record
        # 5 seconds × 16,000 samples/second = 80,000 samples
        samplerate=sample_rate,   # How many samples per second to capture
        channels=1,               # Mono recording — Whisper works with mono audio
        dtype='float32'           # Data type for audio samples — required by Whisper
    )
    
    sounddevice.wait()
    # Blocks execution until recording is complete
    # Without this, the code would continue before audio capture finishes
    # Result would be an empty or partial recording

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Creates a temporary .wav file on disk
        # suffix=".wav" — Whisper requires a file path with a recognisable audio extension
        # delete=False — keeps the file after the with block so Whisper can read it
        # tempfile handles cleanup — no need to manually manage file paths
        
        scipy.io.wavfile.write(f.name, sample_rate, audio)
        # Saves the recorded numpy audio array to the temp file as a WAV
        # f.name is the full path to the temp file e.g. /tmp/tmpXYZ123.wav
        # sample_rate must match what was used during recording
        
        result = model.transcribe(f.name)
        # Passes the WAV file to Whisper for speech-to-text conversion
        # Whisper reads the file, runs inference locally, returns a dictionary
        # result["text"] contains the transcribed text
        # result also contains "segments" and "language" but we only need text
        
        return result["text"].strip()
        # .strip() removes leading/trailing whitespace and newlines
        # Returns clean transcribed text e.g. "What is the weather in London today"