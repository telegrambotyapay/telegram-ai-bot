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

# ---------------- Ses servisleri ----------------
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")

TRANSCRIPTION_PROVIDERS = {
    "auto": {
        "label": "⚙️ Otomatik (önce Deepgram, olmazsa AssemblyAI)",
        "description": (
            "Ekstra ayar gerektirmez. Önce Deepgram'ı dener, o başarısız "
            "olursa otomatik olarak AssemblyAI'a geçer."
        ),
    },
    "deepgram": {
        "label": "🟣 Deepgram",
        "description": "Tek istekle çalışan, hızlı bir konuşma tanıma servisi.",
    },
    "assemblyai": {
        "label": "🔵 AssemblyAI",
        "description": "Yükle-ve-bekle mantığıyla çalışan, güvenilir bir konuşma tanıma servisi.",
    },
}
DEFAULT_TRANSCRIPTION_KEY = "auto"

# ---------------- Görsel/Video servisleri ----------------
GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
FAL_API_KEY = os.getenv("FAL_API_KEY", "")
JSON2VIDEO_API_KEY = os.getenv("JSON2VIDEO_API_KEY", "")
AGNES_API_KEY = os.getenv("AGNES_API_KEY", "")

IMAGE_PROVIDERS = {
    "pollinations_image": {
        "label": "🌸 Pollinations (Görsel)",
        "description": "API anahtarı gerektirmeyen, hızlı ve tamamen ücretsiz görsel üretimi.",
        "kind": "image",
    },
    "gemini_image": {
        "label": "🔷 Gemini (Nano Banana)",
        "description": (
            "Google Gemini'nin görsel üretme modeli. Aynı Google AI Studio "
            "anahtarını kullanır, ayrı bir key gerekmez. Genel amaçlı, "
            "kaliteli görseller üretir."
        ),
        "kind": "image",
    },
    "agnes_image": {
        "label": "🐦 Agnes AI (Görsel)",
        "description": (
            "Aynı Agnes anahtarıyla görsel üretimi. Ücretsiz ama yeni bir "
            "servis, çıktı kalitesi değişken olabilir."
        ),
        "kind": "image",
    },
    "fal": {
        "label": "🖼️ Fal.ai",
        "description": "Flux modeliyle hızlı, yüksek kaliteli AI görsel üretimi.",
        "kind": "image",
    },
    "json2video": {
        "label": "🎬 JSON2Video",
        "description": (
            "Yazdığın metni basit, başlıklı bir video haline getirir. "
            "Render işlemi biraz sürebilir (yarım-iki dakika arası)."
        ),
        "kind": "video",
    },
}
DEFAULT_IMAGE_PROVIDER_KEY = "pollinations_image"

# ---------------- Sağlayıcı adapter tipleri ----------------
# openai_compatible : OpenAI'nin /chat/completions formatını taklit eden servisler
#                      (Groq, Cerebras, SambaNova, Mistral, Hugging Face router)
# gemini            : Google AI Studio (Gemini) REST API
# cohere            : Cohere v2 Chat API
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
        "model_name": "gemini-2.5-flash",
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
        "model_name": "gpt-oss-120b",
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
        "model_name": "command-a-plus-05-2026",
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
    "agnes": {
        "label": "🐦 Agnes AI",
        "description": (
            "Singapur merkezli, süresiz ücretsiz (dakikada 20 istek sınırlı) "
            "çok yönlü bir yapay zeka. Yeni bir servis olduğu için çıktı "
            "kalitesi diğerleri kadar tutarlı olmayabilir."
        ),
        "adapter_type": "openai_compatible",
        "api_key_env": "AGNES_API_KEY",
        "base_url": "https://apihub.agnes-ai.com/v1",
        "model_name": "agnes-2.0-flash",
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
        "providers": list(IMAGE_PROVIDERS.keys()),
        "enabled": True,
        "info_text": (
            "Bir servis seçtiğinde, göndereceğin her mesaj o servise bir "
            "üretim isteği (prompt) olarak gidecek ve sana görsel/video "
            "olarak dönecek.\n\n"
            "Sohbet moduna geri dönmek için /menu → 🤖 Sohbet AI'dan "
            "bir model seçmen yeterli."
        ),
    },
    "voice": {
        "label": "🎙️ Ses İşlemleri",
        "description": "Sesli mesaj yazıya çevirme ve metni sese dönüştürme.",
        "providers": [],
        "enabled": True,
        "info_text": (
            "İstediğin an bana sesli mesaj gönderebilirsin — otomatik "
            "olarak yazıya çevirip aktif yapay zeka modeline soruyorum, "
            "cevabı yazılı olarak alıyorsun.\n\n"
            "Ayrıca her metin cevabının altındaki 🔊 Sesli Dinle butonuyla, "
            "cevabı sesli mesaj olarak da dinleyebilirsin.\n\n"
            "Hangi yapay zekanın cevap vereceği her zaman 🤖 Sohbet AI "
            "kategorisinden seçtiğin aktif modele göre belirlenir. "
            "Aşağıdan da sesli mesajları hangi servisin yazıya çevireceğini "
            "seçebilirsin:"
        ),
    },
    "tools": {
        "label": "🔍 Bilgi & Araçlar",
        "description": "Hava durumu, döviz kuru, arama ve daha fazlası.",
        "providers": [],
        "enabled": False,
    },
}
