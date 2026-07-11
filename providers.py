"""
Her yapay zeka sağlayıcısı farklı bir API formatı kullanır.
Bu modül hepsini tek bir ortak arayüz (generate) altında birleştirir.
"""
from __future__ import annotations
import os
import re
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from abc import ABC, abstractmethod
from typing import List, Dict

import requests
from openai import OpenAI, RateLimitError, InternalServerError

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sen yardımsever, dürüst ve samimi bir Telegram bot asistanısın. "
    "Kullanıcının dilinde (genelde Türkçe) cevap ver. Gerektiğinde "
    "detaylı, gerektiğinde kısa ve net konuş."
)

_TR_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
_TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _today_str_tr() -> str:
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    return f"{now.day} {_TR_MONTHS[now.month - 1]} {now.year}, {_TR_DAYS[now.weekday()]}"


class ProviderError(Exception):
    """Sağlayıcıdan cevap alınamadığında fırlatılır."""


class AIAdapter(ABC):
    def __init__(self, provider_key: str):
        self.provider_key = provider_key
        self.info = config.PROVIDERS[provider_key]
        base_prompt = self.info.get("system_prompt") or SYSTEM_PROMPT
        self.system_prompt = (
            f"{base_prompt}\n\nBugünün tarihi: {_today_str_tr()}. "
            f"Güncel tarih/zamanla ilgili sorularda bunu esas al."
        )
        env_name = self.info.get("api_key_env")
        self.api_key = os.getenv(env_name, "") if env_name else ""
        if env_name and not self.api_key:
            raise ProviderError(
                f"{self.info['label']} için API anahtarı bulunamadı "
                f"({env_name} ortam değişkenini ayarla)."
            )

    @abstractmethod
    def generate(self, history: List[Dict[str, str]], user_message: str) -> str:
        raise NotImplementedError


class OpenAICompatibleAdapter(AIAdapter):
    """Groq, Cerebras, SambaNova, Mistral, Hugging Face (router), Agnes vb."""

    def __init__(self, provider_key: str):
        super().__init__(provider_key)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.info["base_url"],
            max_retries=0,
        )

    def _build_messages(self, history, user_message):
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _parse_tpm_overage(error_str: str):
        """'Limit 8000, Requested 9763' gibi bir hatadan (limit, requested) tuple'ı çıkarır."""
        match = re.search(r"Limit (\d+), Requested (\d+)", error_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

    def generate(self, history, user_message) -> str:
        messages = self._build_messages(history, user_message)

        last_error = None
        for attempt in range(4):
            try:
                response = self.client.chat.completions.create(
                    model=self.info["model_name"],
                    messages=messages,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except (RateLimitError, InternalServerError) as e:
                last_error = e
                logger.warning(f"Geçici hata (rate limit/sunucu), {attempt + 1}. deneme, bekleniyor...")
                time.sleep(4)
            except Exception as e:
                error_str = str(e)
                too_large = (
                    "tokens per minute" in error_str
                    or "Request too large" in error_str
                    or "rate_limit_exceeded" in error_str
                )
                if too_large and len(history) > 2:
                    overage = self._parse_tpm_overage(error_str)
                    if overage:
                        limit, requested = overage
                        # Ne kadar fazlaysa (+ güvenlik payı) o oranda geçmişten kırp,
                        # sabit bir sayıya değil, gerçek fazlalığa göre.
                        cut_ratio = min(0.9, max(0.15, (requested - limit) / requested + 0.15))
                    else:
                        cut_ratio = 0.5
                    new_len = max(2, int(len(history) * (1 - cut_ratio)))
                    if new_len < len(history):
                        logger.warning(
                            f"Mesaj çok büyük (TPM limiti), geçmiş {len(history)} -> {new_len} "
                            f"mesaja kırpılıp tekrar deneniyor..."
                        )
                        history = history[-new_len:]
                        messages = self._build_messages(history, user_message)
                        continue
                logger.exception("OpenAI uyumlu sağlayıcıda hata")
                raise ProviderError(str(e)) from e

        raise ProviderError(
            f"Sunucu şu an çok yoğun (rate limit). Birkaç dakika sonra tekrar dene. ({last_error})"
        )


class GeminiAdapter(AIAdapter):
    def generate(self, history, user_message) -> str:
        contents = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.info['model_name']}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
        }
        last_error = None
        for attempt in range(4):
            try:
                resp = requests.post(url, json=payload, timeout=60)
                if resp.status_code == 403:
                    raise ProviderError(
                        "Gemini 403 hatası: API key yanlış olabilir, Google AI Studio'da "
                        "Gemini API açık olmayabilir ya da bu modele erişimin yok. "
                        "GOOGLE_AI_STUDIO_API_KEY'i kontrol et."
                    )
                if resp.status_code == 404:
                    raise ProviderError(
                        f"Gemini model hatası: '{self.info['model_name']}' modeli bulunamadı. "
                        "Model adı değişmiş olabilir."
                    )
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = f"{resp.status_code} {resp.reason}"
                    kind = "rate limit" if resp.status_code == 429 else "geçici sunucu hatası"
                    logger.warning(f"Gemini {kind}, {attempt + 1}. deneme...")
                    time.sleep(3 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except ProviderError:
                raise
            except requests.HTTPError as e:
                logger.exception("Gemini hata")
                raise ProviderError(str(e)) from e
        raise ProviderError(
            f"Google AI Studio şu an geçici olarak yanıt veremiyor (yoğunluk/sunucu hatası). "
            f"Birkaç dakika sonra tekrar dene. ({last_error})"
        )


class CohereAdapter(AIAdapter):
    """Cohere v2 Chat API."""

    def generate(self, history, user_message) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        try:
            resp = requests.post(
                "https://api.cohere.com/v2/chat",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.info["model_name"], "messages": messages},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"][0]["text"]
        except Exception as e:
            logger.exception("Cohere hata")
            raise ProviderError(str(e)) from e


class PollinationsAdapter(AIAdapter):
    """API anahtarı gerektirmez."""

    def generate(self, history, user_message) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        try:
            resp = requests.post(
                "https://text.pollinations.ai/openai",
                json={"model": self.info["model_name"], "messages": messages},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.exception("Pollinations hata")
            raise ProviderError(str(e)) from e


_ADAPTER_CLASSES = {
    "openai_compatible": OpenAICompatibleAdapter,
    "gemini": GeminiAdapter,
    "cohere": CohereAdapter,
    "pollinations": PollinationsAdapter,
}


def get_adapter(provider_key: str) -> AIAdapter:
    info = config.PROVIDERS[provider_key]
    adapter_cls = _ADAPTER_CLASSES[info["adapter_type"]]
    return adapter_cls(provider_key)
