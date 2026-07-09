# Çoklu Yapay Zeka Telegram Botu — Kurulum Rehberi

Bu rehber kod bilmediğini varsayarak yazıldı. Adımları sırayla takip et.

## Bot Ne Yapıyor — Genel Özellikler

`/menu` komutuyla 4 kategori arasında geziniyorsun:

### 🤖 Sohbet AI (9 model)
Google AI Studio (Gemini), Groq, Cerebras, SambaNova, Mistral, Cohere,
Hugging Face, Pollinations, Agnes AI. Bir model seç, sohbete başla.
Konuşma geçmişi hatırlanır, model değiştirsen bile korunur.

### 🎨 Görsel Üretimi (4 servis)
Pollinations, Gemini (Nano Banana), Agnes AI, JSON2Video (metin → video).
Bir servis seç, ne istediğini yaz, görsel/video olarak al.

**Ayrıca:** İstediğin an, hangi moddaysan ol, bana bir **fotoğraf** gönderirsen
otomatik olarak analiz edip içeriğini anlatırım (Gemini ile) — istersen bu
analizi **Word veya Excel** dosyası olarak da indirebilirsin.

### 🎙️ Ses İşlemleri
Sesli mesaj gönder → otomatik yazıya çevrilip aktif sohbet AI'na sorulur.
Her cevabın altındaki **🔊 Sesli Dinle** butonuyla cevabı sesli de dinleyebilirsin.
Yazıya çevirme servisini (Deepgram / AssemblyAI / Otomatik) menüden seçebilirsin.

### 🔍 Bilgi & Araçlar (7 araç)
Hava Durumu, Döviz Kuru, WolframAlpha, Web Arama (Tavily), Hava Kalitesi,
Link Güvenlik Taraması (VirusTotal), NASA Günün Fotoğrafı.

### Her AI cevabının altında
💾 Kaydet · 🗑️ Hafızayı Temizle · 🔊 Sesli Dinle · 🔄 Yönlendir ·
📄 Word'e Aktar · 📊 Excel'e Aktar

**🔄 Yönlendir** butonu TEK bir listede tüm kategorilerden (sohbet AI,
görsel servisi, ses servisi, araç) seçim sunar — tıkladığın an aktif olur,
cevaplanmamış son mesajın varsa otomatik olarak yeni seçime sorulur.

---

## ADIM 1 — GitHub'a Yükle

1. [github.com](https://github.com) üzerinde ücretsiz hesap aç (yoksa).
2. Yeni, **private** bir repo oluştur (örn. `telegram-ai-bot`).
3. Bu projedeki **tüm dosyaları** yükle: **"Add file" → "Upload files"** ile
   sürükle bırak. Dosya listesi:
   - `bot.py`, `config.py`, `providers.py`, `storage.py`, `voice.py`,
     `image_gen.py`, `document_export.py`, `tools.py`
   - `requirements.txt`, `.env.example`, `README.md`
4. **.env dosyasını ASLA GitHub'a yükleme** — gerçek anahtarların Render'da
   ayrı girilecek (Adım 3).

## ADIM 2 — Supabase Kurulumu (Hafıza)

1. [supabase.com](https://supabase.com) üzerinde ücretsiz hesap/proje aç.
2. **SQL Editor**'a gir, **New query** ile şunu çalıştır:

```sql
create table conversations (
    id bigint generated always as identity primary key,
    user_id bigint not null,
    provider_key text,
    role text not null,
    content text not null,
    created_at timestamp with time zone default now()
);

create index on conversations (user_id);

create table user_settings (
    user_id bigint primary key,
    provider text,
    transcription_provider text,
    mode text,
    image_provider text,
    active_tool text,
    active_astrology_feature text,
    updated_at timestamp with time zone default now()
);
```

Bu ikinci tablo (`user_settings`), hangi model/mod/aracın aktif olduğunu kalıcı olarak
saklar — Render her yeniden başladığında (deploy) bu bilgi sıfırlanmasın diye.

3. **Project Settings → Data API**'de **Project URL**'i,
   **Project Settings → API Keys**'de **anon/public** key'i kopyala.

## ADIM 3 — Render'da Botu Yayınla

1. [render.com](https://render.com) → GitHub hesabınla giriş yap.
2. **New +** → **Web Service** → reponu seç.
3. Ayarlar:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: **Free**
4. **Environment Variables** kısmına aşağıdaki tabloyu tek tek ekle
   (elinde olmayanı hiç ekleme, sorun olmaz — sadece o özellik çalışmaz):

| Anahtar | Ne için |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Zorunlu — BotFather |
| `SUPABASE_URL`, `SUPABASE_KEY` | Kalıcı hafıza |
| `GOOGLE_AI_STUDIO_API_KEY` | Gemini sohbet + görsel üretim/analiz |
| `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `SAMBANOVA_API_KEY`, `MISTRAL_API_KEY`, `COHERE_API_KEY`, `HUGGINGFACE_API_KEY`, `AGNES_API_KEY` | Diğer sohbet AI'ları |
| `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` | Sesli mesaj → yazı |
| `JSON2VIDEO_API_KEY` | Metin → video |
| `OPENWEATHER_API_KEY`, `EXCHANGERATE_API_KEY`, `WOLFRAMALPHA_API_KEY`, `TAVILY_API_KEY`, `AQICN_API_KEY`, `VIRUSTOTAL_API_KEY`, `NASA_API_KEY` | Bilgi & Araçlar |

5. **PYTHON_VERSION** = `3.12.7` ekle (daha yeni sürümlerde uyumluluk sorunu çıkabiliyor).
6. **Create Web Service** de, birkaç dakika bekle, **Logs**'ta
   `Bot başlatılıyor...` yazısını gör.

> Render sana bir URL verecek (örn. `https://xxxx.onrender.com`) — Adım 4'te lazım.

## ADIM 4 — UptimeRobot ile Botu Uyanık Tut

1. [uptimerobot.com](https://uptimerobot.com) → ücretsiz hesap aç.
2. **Add New Monitor** → Type: **HTTP(s)** → URL: Render adresin →
   Interval: **5 minutes** → kaydet.

Render'ın ücretsiz sunucuları 15 dakika hareketsizlikte uyur; UptimeRobot
5 dakikada bir dürttüğü için bot hiç uyumaz.

## ADIM 5 — Botu Kullan

- `/start` — karşılama
- `/menu` — kategori ve model/servis/araç seçimi
- `/reset` — hafızayı tamamen sıfırla
- Herhangi bir an **sesli mesaj** ya da **fotoğraf** gönderebilirsin, hangi
  modda olursan ol otomatik işlenir.

---

## Yeni Bir Servis Eklemek İstersen

Her kategori `config.py` içinde ayrı bir sözlükte tanımlı:
- Sohbet AI → `PROVIDERS`
- Görsel/Video → `IMAGE_PROVIDERS`
- Ses (transkripsiyon) → `TRANSCRIPTION_PROVIDERS`
- Araçlar → `TOOL_PROVIDERS`

Yeni bir kayıt ekleyip ilgili dosyada (`providers.py`, `image_gen.py`,
`voice.py`, `tools.py`) karşılık gelen fonksiyonu/adapter'ı yazman yeterli.
`bot.py`'deki menü/callback sistemi bu sözlükleri otomatik okuyor.

## Sorun Giderme

- **Bot hiç cevap vermiyor**: Render **Logs**'a bak. `TELEGRAM_BOT_TOKEN`
  yanlış olabilir, ya da bir dosya eksik/eski kalmış olabilir — bu durumda
  GitHub'daki tüm dosyaları bu paketle yeniden değiştir.
- **Bir model/servis hep hata veriyor**: İlgili API key'i eksik/yanlış
  olabilir, ya da servis sağlayıcı model adını değiştirmiş olabilir.
- **Hafıza kaydolmuyor**: Supabase URL/KEY yanlış olabilir ya da SQL
  Editor'daki tabloyu oluşturmayı unutmuş olabilirsin (Adım 2).
- **"AttributeError" / "SyntaxError" gibi hatalar**: Neredeyse her zaman
  GitHub'daki dosyalardan biri eksik/eski/yarım yapıştırılmış demektir —
  o dosyayı tamamen silip bu paketteki güncel haliyle değiştir.
