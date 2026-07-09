"""
Görsel ve video üretimi:
- generate_pollinations_image(): API anahtarı gerektirmez
- generate_gemini_image(): Google Gemini (Nano Banana) ile görsel üretimi
- generate_agnes_image(): Agnes AI ile görsel üretimi
- generate_json2video(): Basit, başlıklı bir metin videosu oluşturur
- analyze_image_gemini(): Gönderilen bir görseli Gemini ile analiz eder
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
        f"gemini-3.1-flash-lite-image:generateContent?key={config.GOOGLE_AI_STUDIO_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image", "text"]},
    }
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 429:
                last_error = "429 Too Many Requests"
                logger.warning(f"Gemini görsel rate limit, {attempt + 1}. deneme...")
                time.sleep(3 * (attempt + 1))
                continue
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
        except requests.HTTPError as e:
            raise ImageGenError(f"Gemini görsel üretimi başarısız: {e}") from e
    raise ImageGenError(f"Gemini şu an çok yoğun (rate limit). ({last_error})")


def generate_agnes_image(prompt: str) -> bytes:
    if not config.AGNES_API_KEY:
        raise ImageGenError("AGNES_API_KEY tanımlı değil.")
    try:
        resp = requests.post(
            "https://apihub.agnes-ai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {config.AGNES_API_KEY}"},
            json={"model": "agnes-image-2.1-flash", "prompt": prompt, "size": "1024x1024"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        item = data["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            img_resp = requests.get(item["url"], timeout=60)
            img_resp.raise_for_status()
            return img_resp.content
        raise ImageGenError("Agnes cevabında görsel verisi bulunamadı.")
    except ImageGenError:
        raise
    except Exception as e:
        raise ImageGenError(f"Agnes görsel üretimi başarısız: {e}") from e


def generate_json2video(prompt: str) -> bytes:
    if not config.JSON2VIDEO_API_KEY:
        raise ImageGenError("JSON2VIDEO_API_KEY tanımlı değil.")

    movie_payload = {
        "resolution": "sd",
        "scenes": [
            {
                "background-color": "#1a1a2e",
                "elements": [
                    {"type": "text", "text": prompt[:300], "style": "003", "duration": 6}
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
    for _ in range(24):
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


def analyze_image_gemini(image_bytes: bytes, instruction: str = None, mime_type: str = "image/jpeg") -> str:
    """Gönderilen bir görseli Gemini ile analiz eder/yorumlar, metin döner."""
    if not config.GOOGLE_AI_STUDIO_API_KEY:
        raise ImageGenError("GOOGLE_AI_STUDIO_API_KEY tanımlı değil (görsel analizi için gerekli).")
    prompt = instruction or (
        "Bu görseli ayrıntılıca anlat: içinde ne olduğunu tarif et. Eğer görselde "
        "yazı/metin varsa aynen aktar. Bir tablo, liste, fatura ya da makbuz gibi "
        "yapılandırılmış bir içerikse, bunu düzenli satırlar halinde, mümkünse "
        "sütunları birbirinden '|' işaretiyle ayırarak belirt."
    )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={config.GOOGLE_AI_STUDIO_API_KEY}"
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": b64}},
            ]
        }]
    }
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 429:
                last_error = "429 Too Many Requests"
                logger.warning(f"Gemini analiz rate limit, {attempt + 1}. deneme...")
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            text_out = "".join(p.get("text", "") for p in parts if p.get("text"))
            if not text_out.strip():
                raise ImageGenError("Gemini cevabında metin bulunamadı.")
            return text_out
        except ImageGenError:
            raise
        except requests.HTTPError as e:
            raise ImageGenError(f"Gemini görsel analizi başarısız: {e}") from e
    raise ImageGenError(f"Gemini şu an çok yoğun (rate limit). ({last_error})")
