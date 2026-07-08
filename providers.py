"""
Her yapay zeka sağlayıcısı farklı bir API formatı kullanır.
Bu modül hepsini tek bir ortak arayüz (generate) altında birleştirir.
"""
from __future__ import annotations
import os
import logging
from abc import ABC, abstractmethod
from typing import List, Dict

import requests
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sen yardımsever, dürüst ve samimi bir Telegram bot asistanısın. "
    "Kullanıcının dilinde (genelde Türkçe) cevap ver. Gerektiğinde "
    "detaylı, gerektiğinde kısa ve net konuş."
)


class ProviderError(Exception):
    """Sağlayıcıdan cevap alınamadığında fırlatılır."""


class AIAdapter(ABC):
    def __init__(self, provider_key: str):
        self.provider_key = provider_key
        self.info = config.PROVIDERS[provider_key]
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
    """Groq, Cerebras, OpenRouter, SambaNova, Mistral, DeepSeek vb."""

    def __init__(self, provider_key: str):
        super().__init__(provider_key)
        self.client = OpenAI(api_key=self.api_key, base_url=self.info["base_url"])

    def generate(self, history, user_message) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        try:
            response = self.client.chat.completions.create(
                model=self.info["model_name"],
                messages=messages,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.exception("OpenAI uyumlu sağlayıcıda hata")
            raise ProviderError(str(e)) from e


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
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        }
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.exception("Gemini hata")
            raise ProviderError(str(e)) from e


class CohereAdapter(AIAdapter):
    def generate(self, history, user_message) -> str:
        chat_history = [
            {
                "role": "CHATBOT" if msg["role"] == "assistant" else "USER",
                "message": msg["content"],
            }
            for msg in history
        ]
        try:
            resp = requests.post(
                "https://api.cohere.com/v1/chat",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.info["model_name"],
                    "message": user_message,
                    "chat_history": chat_history,
                    "preamble": SYSTEM_PROMPT,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["text"]
        except Exception as e:
            logger.exception("Cohere hata")
            raise ProviderError(str(e)) from e


class HuggingFaceAdapter(AIAdapter):
    def generate(self, history, user_message) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        try:
            resp = requests.post(
                "https://api-inference.huggingface.co/models/"
                f"{self.info['model_name']}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.info["model_name"], "messages": messages},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.exception("Hugging Face hata")
            raise ProviderError(str(e)) from e


class PollinationsAdapter(AIAdapter):
    """API anahtarı gerektirmez."""

    def generate(self, history, user_message) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
    "huggingface": HuggingFaceAdapter,
    "pollinations": PollinationsAdapter,
}


def get_adapter(provider_key: str) -> AIAdapter:
    info = config.PROVIDERS[provider_key]
    adapter_cls = _ADAPTER_CLASSES[info["adapter_type"]]
    return adapter_cls(provider_key)
