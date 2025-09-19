import hashlib
from pathlib import Path
from django.conf import settings
from .models import MediaAsset


def text_key(text: str, lang_code: str, voice: str = "default") -> str:
    raw = f"{lang_code}::{voice}::{(text or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_tts_mp3(text: str, lang_code: str = "ln", voice: str = "default", item=None) -> MediaAsset:
    """
    Generate (or fetch from cache) a TTS MP3 for the given text.
    Returns a MediaAsset pointing to /media/audio/<hash>.mp3
    """
    try:
        from gtts import gTTS  # lazy import so app can start without gTTS installed
    except Exception as e:
        raise RuntimeError("gTTS is not installed. Install it to use TTS (pip install gTTS).") from e
    h = text_key(text, lang_code, voice)
    existing = MediaAsset.objects.filter(kind="tts", text_hash=h, lang_code=lang_code).first()
    if existing:
        return existing

    out_dir = Path(settings.MEDIA_ROOT) / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{h}.mp3"

    # gTTS supports 'ln' for Lingala
    tts = gTTS(text=text, lang=lang_code)
    tts.save(str(out_path))

    asset = MediaAsset.objects.create(
        kind="tts", lang_code=lang_code, text_hash=h, text=text, item=item
    )
    # Set the FileField path relative to MEDIA_ROOT
    asset.file.name = f"audio/{h}.mp3"
    asset.save()
    return asset
