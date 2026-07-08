"""
Görsel ve video üretimi:
- generate_pollinations_image(): API anahtarı gerektirmez
- generate_gemini_image(): Google Gemini (Nano Banana) ile görsel üretimi
- generate_fal_image(): Fal.ai (Flux) ile hızlı görsel üretimi
- generate_json2video(): Basit, başlıklı bir metin videosu oluşturur
"""
import time
import base64
import logging
from urllib.parse import quote

import requests

import config

logger = logging.getLogger(__name__)


class ImageGenError(Exception):
    """Görsel/video üretimi başarısız olduğunda fırlatılır."""


def generate_pollinations_image(prompt: str) -> bytes:
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1024&height=1024&nologo=true"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        raise ImageGenError(f"Pollinations görsel üretimi başarısız: {e}") from e


def generate_gemini_image(prompt: str) -> bytes:
    if not config.GOOGLE_AI_STUDIO_API_KEY:
        raise ImageGenError("GOOGLE_AI_STUDIO_API_KEY tanımlı değil.")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash-image:generateContent?key={config.GOOGLE_AI_STUDIO_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image", "text"]},
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
        raise ImageGenError("Gemini cevabında görsel verisi bulunamadı.")
    except ImageGenError:
        raise
    except Exception as e:
        raise ImageGenError(f"Gemini görsel üretimi başarısız: {e}") from e


def generate_fal_image(prompt: str) -> bytes:
    if not config.FAL_API_KEY:
        raise ImageGenError("FAL_API_KEY tanımlı değil.")
    try:
        resp = requests.post(
            "https://fal.run/fal-ai/flux/schnell",
            headers={"Authorization": f"Key {config.FAL_API_KEY}"},
            json={"prompt": prompt},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data["images"][0]["url"]
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
    except ImageGenError:
        raise
    except Exception as e:
        raise ImageGenError(f"Fal.ai görsel üretimi başarısız: {e}") from e


def generate_json2video(prompt: str) -> bytes:
    """Basit, tek sahnelik, metin gösteren bir video oluşturur (render birkaç dakika sürebilir)."""
    if not config.JSON2VIDEO_API_KEY:
        raise ImageGenError("JSON2VIDEO_API_KEY tanımlı değil.")

    movie_payload = {
        "resolution": "sd",
        "scenes": [
            {
                "background-color": "#1a1a2e",
                "elements": [
                    {
                        "type": "text",
                        "text": prompt[:300],
                        "style": "003",
                        "duration": 6,
                    }
                ],
            }
        ],
    }
    headers = {"x-api-key": config.JSON2VIDEO_API_KEY, "Content-Type": "application/json"}

    try:
        submit_resp = requests.post(
            "https://api.json2video.com/v2/movies", headers=headers, json=movie_payload, timeout=30
        )
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        project_id = submit_data.get("project") or submit_data.get("movie", {}).get("project")
        if not project_id:
            raise ImageGenError(f"JSON2Video proje kimliği alınamadı: {submit_data}")
    except ImageGenError:
        raise
    except Exception as e:
        raise ImageGenError(f"JSON2Video isteği başarısız: {e}") from e

    status_url = f"https://api.json2video.com/v2/movies?project={project_id}"
    for _ in range(24):  # en fazla ~2 dakika bekle (24 x 5sn)
        time.sleep(5)
        try:
            poll_resp = requests.get(status_url, headers=headers, timeout=30)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()
            movie = poll_data.get("movie", {})
            status = movie.get("status")
            if status == "done":
                video_url = movie["url"]
                video_resp = requests.get(video_url, timeout=90)
                video_resp.raise_for_status()
                return video_resp.content
            if status == "error":
                raise ImageGenError(movie.get("message", "JSON2Video render hatası"))
        except ImageGenError:
            raise
        except Exception as e:
            logger.warning(f"JSON2Video durum kontrolünde hata: {e}")

    raise ImageGenError("JSON2Video render işlemi zaman aşımına uğradı (2 dakika).")
