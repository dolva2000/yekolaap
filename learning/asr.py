from typing import Optional

def transcribe_local(path: str) -> Optional[str]:
    """
    Try to transcribe an audio file using local Whisper if installed.
    Returns the transcription text or None on failure.
    Note: Requires ffmpeg and openai-whisper.
    """
    try:
        import whisper  # type: ignore
        model = whisper.load_model("base")
        result = model.transcribe(path, language="ln")
        return (result.get("text") or "").strip()
    except Exception:
        return None
