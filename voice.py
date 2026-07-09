"""
Ses işlemleri:
- transcribe(): sesli mesajı yazıya çevirir (Deepgram / AssemblyAI / otomatik)
- synthesize_speech(): metni sese çevirir (gTTS, API anahtarı gerektirmez)
"""
import time
import logging
import tempfile

import requests
from gtts import gTTS

import config

logger = logging.getLogger(__name__)


class VoiceError(Exception):
    """Ses işlemi (transkripsiyon veya sentezleme) başarısız olduğunda fırlatılır."""


def _transcribe_deepgram(audio_bytes: bytes) -> str:
    resp = requests.post(
        "https://api.deepgram.com/v1/listen?smart_format=true&language=tr",
        headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}", "Content-Type": "audio/ogg"},
        data=audio_bytes,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["results"]["channels"][0]["alternatives"][0]["transcript"]


def _transcribe_assemblyai(audio_bytes: bytes) -> str:
    upload_resp = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": config.ASSEMBLYAI_API_KEY},
        data=audio_bytes,
        timeout=60,
    )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]

    submit_resp = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={"authorization": config.ASSEMBLYAI_API_KEY},
        json={"audio_url": upload_url},
        timeout=60,
    )
    submit_resp.raise_for_status()
    transcript_id = submit_resp.json()["id"]

    status_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    for _ in range(30):
        poll_resp = requests.get(status_url, headers={"authorization": config.ASSEMBLYAI_API_KEY}, timeout=30)
        poll_resp.raise_for_status()
        result = poll_resp.json()
        if result["status"] == "completed":
            return result["text"]
        if result["status"] == "error":
            raise VoiceError(result.get("error", "AssemblyAI hata verdi"))
        time.sleep(2)

    raise VoiceError("AssemblyAI zaman aşımına uğradı (60 saniye).")


def transcribe(audio_bytes: bytes, preferred: str = "auto") -> str:
    """
    preferred: "auto" (Deepgram dener, olmazsa AssemblyAI'a düşer),
               "deepgram" (sadece Deepgram), "assemblyai" (sadece AssemblyAI).
    """
    if preferred == "deepgram":
        if not config.DEEPGRAM_API_KEY:
            raise VoiceError("Deepgram seçili ama DEEPGRAM_API_KEY tanımlı değil.")
        return _transcribe_deepgram(audio_bytes)

    if preferred == "assemblyai":
        if not config.ASSEMBLYAI_API_KEY:
            raise VoiceError("AssemblyAI seçili ama ASSEMBLYAI_API_KEY tanımlı değil.")
        return _transcribe_assemblyai(audio_bytes)

    if config.DEEPGRAM_API_KEY:
        try:
            return _transcribe_deepgram(audio_bytes)
        except Exception as e:
            logger.warning(f"Deepgram başarısız ({e}), AssemblyAI deneniyor...")
            if not config.ASSEMBLYAI_API_KEY:
                raise VoiceError(f"Deepgram hata verdi: {e}") from e

    if config.ASSEMBLYAI_API_KEY:
        return _transcribe_assemblyai(audio_bytes)

    raise VoiceError(
        "Sesli mesajları yazıya çevirmek için DEEPGRAM_API_KEY ya da "
        "ASSEMBLYAI_API_KEY ortam değişkenlerinden biri tanımlanmalı."
    )


def synthesize_speech(text: str) -> str:
    """Metni sese çevirir, geçici bir mp3 dosya yolu döner. API anahtarı gerektirmez."""
    safe_text = text[:3000]
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        tts = gTTS(text=safe_text, lang="tr")
        tts.save(tmp.name)
    except Exception as e:
        raise VoiceError(f"Sese çevirme başarısız: {e}") from e
    return tmp.name
