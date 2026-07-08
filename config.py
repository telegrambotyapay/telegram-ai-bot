"""
Merkezi konfigürasyon dosyası.

Yeni bir sağlayıcı eklemek için PROVIDERS sözlüğüne yeni bir kayıt eklemen
ve providers.py içinde ilgili adapter_type'ın işlendiğinden emin olman yeterli.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------- Telegram ----------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ---------------- Supabase (hafıza) ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ---------------- Health check sunucusu (UptimeRobot için) ----------------
HEALTH_CHECK_PORT = int(os.getenv("PORT", "10000"))

# ---------------- Konuşma hafızası ayarları ----------------
MAX_HISTORY_MESSAGES = 20  # Bağlam olarak modele gönderilecek son N mesaj

# ---------------- Sağlayıcı adapter tipleri ----------------
# openai_compatible : OpenAI'nin /chat/completions formatını taklit eden servisler
# gemini            : Google AI Studio (Gemini) REST API
# cohere            : Cohere Chat API
# huggingface       : Hugging Face Inference API
# pollinations      : Key gerektirmeyen, text.pollinations.ai

PROVIDERS = {
    "google": {
        "label": "🔷 Google AI Studio (Gemini)",
        "description": (
            "Google'ın Gemini modeli. Geniş bağlam penceresi, genel amaçlı "
            "güçlü bir sohbet asistanı. Ücretsiz kotası cömerttir."
        ),
        "adapter_type": "gemini",
        "api_key_env": "GOOGLE_AI_STUDIO_API_KEY",
        "model_name": "gemini-2.0-flash",
    },
    "groq": {
        "label": "⚡ Groq",
        "description": (
            "Açık kaynaklı modelleri (Llama vb.) inanılmaz hızlı çalıştırır. "
            "Cevap hızı önemliyse en iyi seçim."
        ),
        "adapter_type": "openai_compatible",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model_name": "llama-3.3-70b-versatile",
    },
    "cerebras": {
        "label": "🧠 Cerebras",
        "description": (
            "Groq'a benzer şekilde açık kaynak modelleri çok yüksek hızda "
            "çalıştıran bir servis."
        ),
        "adapter_type": "openai_compatible",
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "model_name": "llama3.1-8b",
    },
    "openrouter": {
        "label": "🔀 OpenRouter",
        "description": (
            "Tek API üzerinden onlarca farklı modele erişim sağlar. "
            "Bazı modelleri tamamen ücretsizdir."
        ),
        "adapter_type": "openai_compatible",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "model_name": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "sambanova": {
        "label": "🌐 SambaNova",
        "description": "Llama modellerini hızlı ve ücretsiz kotayla sunan bir başka servis.",
        "adapter_type": "openai_compatible",
        "api_key_env": "SAMBANOVA_API_KEY",
        "base_url": "https://api.sambanova.ai/v1",
        "model_name": "Meta-Llama-3.3-70B-Instruct",
    },
    "mistral": {
        "label": "🌬️ Mistral",
        "description": "Fransız Mistral AI'nin kendi modelleri. Dengeli ve hızlı.",
        "adapter_type": "openai_compatible",
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "model_name": "mistral-small-latest",
    },
    "cohere": {
        "label": "🟨 Cohere",
        "description": "Kurumsal odaklı Command modelleri, ücretsiz deneme kotası sunar.",
        "adapter_type": "cohere",
        "api_key_env": "COHERE_API_KEY",
        "model_name": "command-r-plus",
    },
    "huggingface": {
        "label": "🤗 Hugging Face",
        "description": "Binlerce açık kaynak modelden birine ücretsiz erişim.",
        "adapter_type": "openai_compatible",
        "api_key_env": "HUGGINGFACE_API_KEY",
        "base_url": "https://router.huggingface.co/v1",
        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
    },
    "pollinations": {
        "label": "🌸 Pollinations",
        "description": "API anahtarı gerektirmeyen, tamamen ücretsiz basit bir sohbet modeli.",
        "adapter_type": "pollinations",
        "api_key_env": None,
        "model_name": "openai",
    },
}

DEFAULT_PROVIDER_KEY = "google"

# ---------------- Kategoriler (ana /menu yapısı) ----------------
CATEGORIES = {
    "chat": {
        "label": "🤖 Sohbet AI",
        "description": "Bir yapay zeka modeli seç ve onunla sohbete başla.",
        "providers": list(PROVIDERS.keys()),
        "enabled": True,
    },
    "image": {
        "label": "🎨 Görsel Üretimi",
        "description": "Metinden görsel/video üretimi.",
        "providers": [],
        "enabled": False,
    },
    "voice": {
        "label": "🎙️ Ses İşlemleri",
        "description": "Sesli mesaj yazıya çevirme ve metni sese dönüştürme.",
        "providers": [],
        "enabled": False,
    },
    "tools": {
        "label": "🔍 Bilgi & Araçlar",
        "description": "Hava durumu, döviz kuru, arama ve daha fazlası.",
        "providers": [],
        "enabled": False,
    },
}
