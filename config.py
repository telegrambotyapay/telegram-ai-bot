"""
Merkezi konfigürasyon dosyası.
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
MAX_HISTORY_MESSAGES = 20

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
JSON2VIDEO_API_KEY = os.getenv("JSON2VIDEO_API_KEY", "")
AGNES_API_KEY = os.getenv("AGNES_API_KEY", "")

IMAGE_PROVIDERS = {
    "pollinations_image": {
        "label": "🌸 Pollinations (Görsel)",
        "description": "API anahtarı gerektirmeyen, hızlı ve tamamen ücretsiz görsel üretimi.",
        "kind": "image",
    },
    "gemini_image": {
        "label": "🔷 Gemini (Nano Banana 2)",
        "description": (
            "Google Gemini'nin en güncel görsel üretme modeli. Aynı Google "
            "AI Studio anahtarını kullanır, ayrı bir key gerekmez. "
            "⚠️ Kaliteli ama ücretsiz kotası dar olabilir, yoğun saatlerde "
            "rate limit hatası alırsan Pollinations ya da Agnes'i dene."
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

# ---------------- Bilgi & Araçlar servisleri ----------------
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
WOLFRAMALPHA_API_KEY = os.getenv("WOLFRAMALPHA_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
AQICN_API_KEY = os.getenv("AQICN_API_KEY", "")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")
NASA_API_KEY = os.getenv("NASA_API_KEY", "")
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "")
FACEPP_API_KEY = os.getenv("FACEPP_API_KEY", "")
FACEPP_API_SECRET = os.getenv("FACEPP_API_SECRET", "")

TOOL_PROVIDERS = {
    "weather": {
        "label": "🌦️ Hava Durumu",
        "description": "Bir şehir adı yaz (örn. 'İstanbul'), güncel hava durumunu getireyim.",
    },
    "exchange": {
        "label": "💱 Döviz Kuru",
        "description": "Örn. 'USD TRY' ya da '100 USD TRY' yaz, kuru/çeviriyi getireyim.",
    },
    "wolfram": {
        "label": "🧮 WolframAlpha",
        "description": "Matematik, bilim, hesaplama sorularını yanıtlar. Örn. '2x+5=15' ya da 'ışık hızı'.",
    },
    "search": {
        "label": "🔍 Web Arama",
        "description": "Güncel bir konuyu ara, özet sonuçları getireyim.",
    },
    "air": {
        "label": "🌬️ Hava Kalitesi",
        "description": "Bir şehir adı yaz, hava kalitesi endeksini (AQI) getireyim.",
    },
    "virustotal": {
        "label": "🛡️ Link Güvenlik Taraması",
        "description": "Bir link/URL yaz, güvenli olup olmadığını kontrol edeyim.",
    },
    "nasa": {
        "label": "🚀 NASA Günün Fotoğrafı",
        "description": "NASA'nın bugünkü astronomi fotoğrafını getirir. Seçince direkt gelir.",
    },
    "link_summary": {
        "label": "🔗 Link Özetle",
        "description": "Bir web sayfası linki yaz, içeriğini okuyup özetleyeyim.",
    },
    "face_analysis": {
        "label": "😀 Yüz Analizi",
        "description": (
            "Bunu seçtikten sonra bana bir FOTOĞRAF gönder — içindeki "
            "yüzleri analiz edip yaş, cinsiyet ve duygu tahmini vereyim."
        ),
    },
}

# ---------------- Astroloji servisleri ----------------
ASTROLOGY_API_IO_KEY = os.getenv("ASTROLOGY_API_IO_KEY", "")
FREEASTROLOGY_API_KEY = os.getenv("FREEASTROLOGY_API_KEY", "")

ASTROLOGY_FEATURES = {
    "daily": {
        "label": "☀️ Günlük Burç Yorumu",
        "description": "Burcunu yaz (örn. 'Koç'), günlük yorumunu getireyim.",
    },
    "weekly": {
        "label": "📅 Haftalık Burç Yorumu",
        "description": "Burcunu yaz, haftalık yorumunu getireyim.",
    },
    "monthly": {
        "label": "🗓️ Aylık Burç Yorumu",
        "description": "Burcunu yaz, aylık yorumunu getireyim.",
    },
    "yearly": {
        "label": "🎉 Yıllık Burç Yorumu",
        "description": "Burcunu yaz, yıllık yorumunu getireyim.",
    },
    "birthchart": {
        "label": "🌌 Doğum Haritası",
        "description": (
            "Doğum tarihi, saati ve yerini şu formatta yaz:\n"
            "GG.AA.YYYY SS:DD Şehir\nÖrnek: 15.03.1990 14:30 İstanbul"
        ),
    },
}

# ---------------- Sağlayıcı adapter tipleri ----------------
# openai_compatible : OpenAI'nin /chat/completions formatını taklit eden servisler
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
        "model_name": "gemini-3.5-flash",
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
    "vet_assistant": {
        "label": "🐾 Veteriner Asistanı",
        "description": (
            "Evcil/çiftlik hayvanlarının sağlığı, beslenmesi, davranışı ve "
            "bakımı hakkında genel bilgi verir. ⚠️ Gerçek bir veteriner "
            "hekimin yerini tutmaz — teşhis koymaz, ilaç dozu önermez. "
            "Ciddi/acil durumlarda seni gerçek bir veterinere yönlendirir."
        ),
        "adapter_type": "gemini",
        "api_key_env": "GOOGLE_AI_STUDIO_API_KEY",
        "model_name": "gemini-3.5-flash",
        "system_prompt": (
            "Sen deneyimli, bilgili bir veteriner asistanısın. Kullanıcılara "
            "evcil ve çiftlik hayvanlarının sağlığı, beslenmesi, davranışları "
            "ve genel bakımı hakkında Türkçe, anlaşılır bilgi veriyorsun.\n\n"
            "ÇOK ÖNEMLİ KURALLAR:\n"
            "- Sen gerçek bir veteriner hekimin yerini TUTMAZSIN. Kesin teşhis "
            "koymazsın, reçete/ilaç dozu önermezsin.\n"
            "- Kullanıcı ciddi ya da acil olabilecek bir belirti tarif ederse "
            "(nefes darlığı, aşırı kanama, zehirlenme şüphesi, bilinç kaybı, "
            "şiddetli travma, uzun süreli kusma/ishal vb.) onu HEMEN gerçek "
            "bir veteriner hekime veya en yakın acil hayvan kliniğine "
            "yönlendir, bunu cevabının başında belirt.\n"
            "- Genel bilgilendirme ve ilk yönlendirme yap, ama her zaman "
            "kesin tanı ve tedavi için gerçek bir veterinere gitmeleri "
            "gerektiğini hatırlat.\n"
            "- Emin olmadığın konularda spekülasyon yapmak yerine bunu açıkça "
            "belirt."
        ),
    },
}

DEFAULT_PROVIDER_KEY = "google"

# ---------------- Kategoriler (ana /menu yapısı) ----------------
CATEGORIES = {
    "chat": {
        "label": "🤖 Sohbet AI",
        "description": "Bir yapay zeka modeli seç ve onunla sohbete başla.",
        "providers": [k for k in PROVIDERS.keys() if k != "vet_assistant"],
        "enabled": True,
    },
    "vet": {
        "label": "🐾 Veteriner Asistanı",
        "description": "Evcil/çiftlik hayvanı sağlığı, beslenmesi ve bakımı hakkında bilgi al.",
        "providers": ["vet_assistant"],
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
            "🔍 Ayrıca istediğin an (hangi modda olursan ol) bana bir "
            "FOTOĞRAF gönderebilirsin — otomatik olarak analiz edip "
            "içeriğini anlatırım, istersen Word veya Excel dosyası olarak "
            "da indirebilirsin.\n\n"
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
        "enabled": True,
        "info_text": (
            "Bir araç seç, sonra ne istediğini yaz (şehir adı, döviz çifti, "
            "arama konusu, link vb.) — sonucu direkt getireyim.\n\n"
            "Sohbet moduna dönmek için /menu → 🤖 Sohbet AI'dan bir model seç."
        ),
    },
    "files": {
        "label": "📁 Dosya İşlemleri",
        "description": "PDF, Word, Excel, CSV ve metin dosyalarını okuma ve analiz.",
        "providers": [],
        "enabled": True,
        "info_text": (
            "İstediğin an (hangi modda olursan ol) bana bir **PDF, Word (.docx), "
            "Excel (.xlsx), CSV ya da metin (.txt)** dosyası gönderebilirsin — "
            "içeriğini okuyup özetler/analiz ederim.\n\n"
            "Dosyayı gönderirken altyazı (caption) olarak özel bir talimat da "
            "yazabilirsin (örn. 'bu tablodaki toplamı hesapla').\n\n"
            "Cevabın altındaki 📄 Word'e Aktar / 📊 Excel'e Aktar butonlarıyla "
            "sonucu indirebilirsin."
        ),
    },
    "astrology": {
        "label": "🔮 Astroloji",
        "description": "Burç yorumları ve doğum haritası.",
        "providers": [],
        "enabled": True,
        "info_text": (
            "Bir özellik seç:\n\n"
            "☀️/📅/🗓️/🎉 Burç yorumları için sadece burcunu yazman yeterli.\n"
            "🌌 Doğum haritası için tarih, saat ve doğum yerini gireceksin.\n\n"
            "Not: Doğum haritası hesaplaması sınırlı kotaya sahip bir dış "
            "servis kullanıyor, yoğun saatlerde biraz gecikebilir."
        ),
    },
    "reminder": {
        "label": "⏰ Hatırlatıcı",
        "description": "Tek seferlik ya da tekrarlayan (günlük/haftalık/aylık) hatırlatma kur.",
        "providers": [],
        "enabled": True,
        "info_text": (
            "Aşağıdan bir tür seç: tek seferlik, her gün, haftanın belirli "
            "bir günü, ya da ayın belirli bir günü. Sonra saat ve mesajını "
            "soracağım.\n\n"
            "📋 Kurduğun hatırlatıcıları görmek/iptal etmek için "
            "'Hatırlatıcılarımı Listele/Sil' butonunu kullan.\n\n"
            "Not: Tek seferlik hatırlatıcılar bot yeniden başlarsa "
            "(deploy) kaybolur; tekrarlayan (günlük/haftalık/aylık) "
            "hatırlatıcılar da aynı şekilde bot yeniden başladığında "
            "sıfırlanır, yeniden kurman gerekir."
        ),
    },
}
