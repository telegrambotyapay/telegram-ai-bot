# Çoklu Yapay Zeka Telegram Botu — Kurulum Rehberi

Bu rehber kod bilmediğini varsayarak yazıldı. Adımları sırayla takip et.

## Genel Bakış — Hangi Servis Ne İşe Yarıyor

| Servis | Görevi |
|---|---|
| **GitHub** | Kodun saklandığı yer, Render buradan çeker |
| **Render** | Botu 7/24 çalıştıran sunucu (ücretsiz) |
| **Supabase** | Konuşma geçmişini kalıcı saklayan veritabanı (ücretsiz) |
| **UptimeRobot** | Render'ın uykuya dalmasını engelleyen "ping" servisi (ücretsiz) |

---

## ADIM 1 — GitHub'a Yükle

1. [github.com](https://github.com) üzerinde ücretsiz hesap aç (yoksa).
2. Sağ üstten **New repository** ile `telegram-ai-bot` adında yeni, **private** bir repo oluştur.
3. Bu projedeki tüm dosyaları (bot.py, config.py, providers.py, storage.py, requirements.txt, .env.example) bu repoya yükle. En kolay yol: repo sayfasında **"Add file" → "Upload files"** ile dosyaları sürükle bırak.
4. **.env dosyasını ASLA GitHub'a yükleme** — zaten oluşturmadık, sadece `.env.example` var. Gerçek API anahtarların Render'da ayrı girilecek (Adım 3).

## ADIM 2 — Supabase Kurulumu (Hafıza)

1. [supabase.com](https://supabase.com) üzerinde ücretsiz hesap aç, **New Project** oluştur (kredi kartı istemez).
2. Proje açıldıktan sonra sol menüden **SQL Editor**'a gir, **New query** ile şunu yapıştırıp **Run** de:

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
```

3. Sol menüden **Project Settings → API** sayfasına git. Burada iki şeyi kopyala:
   - **Project URL** → bu senin `SUPABASE_URL` değerin
   - **anon public** anahtarı → bu senin `SUPABASE_KEY` değerin

Bunları bir kenara not et, Adım 3'te Render'a gireceksin.

## ADIM 3 — Render'da Botu Yayınla

1. [render.com](https://render.com) üzerinde ücretsiz hesap aç, GitHub hesabınla giriş yap.
2. **New +** → **Web Service** seç.
3. Az önce oluşturduğun `telegram-ai-bot` reposunu seç.
4. Ayarlar:
   - **Name**: istediğin bir isim
   - **Region**: sana en yakın olan
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: **Free** seç
5. **Environment Variables** bölümüne şunları tek tek ekle (Key/Value şeklinde):
   - `TELEGRAM_BOT_TOKEN` → BotFather'dan aldığın token
   - `SUPABASE_URL` → Adım 2'de kopyaladığın URL
   - `SUPABASE_KEY` → Adım 2'de kopyaladığın anon key
   - Elindeki her AI servisinin key'ini de `.env.example` dosyasındaki isimlerle aynen ekle (örn. `GROQ_API_KEY`, `MISTRAL_API_KEY` vb.). Bir servisin key'i yoksa o satırı hiç ekleme — sadece o model butonuna basıldığında hata verir, botun geri kalanı etkilenmez.
6. **Create Web Service** butonuna bas. Render otomatik olarak build edip botu başlatacak (birkaç dakika sürer).
7. Loglarda `Bot başlatılıyor...` yazısını görürsen bot çalışıyor demektir. Telegram'da botuna `/start` yazarak test et.

> Not: Render sana bir URL verecek (örn. `https://telegram-ai-bot.onrender.com`). Bu URL'yi Adım 4'te UptimeRobot'a gireceksin.

## ADIM 4 — UptimeRobot ile Botu Uyanık Tut

Render'ın ücretsiz sunucuları 15 dakika istek almazsa uykuya dalar. Bunu engellemek için:

1. [uptimerobot.com](https://uptimerobot.com) üzerinde ücretsiz hesap aç.
2. **Add New Monitor** de.
3. **Monitor Type**: HTTP(s)
4. **URL**: Render'ın sana verdiği adres (Adım 3, madde 7)
5. **Monitoring Interval**: 5 dakika
6. Kaydet.

Artık UptimeRobot her 5 dakikada bir botunu "dürtecek" ve Render onu hiç uyutmayacak.

## ADIM 5 — Botu Kullan

Telegram'da botuna:
- `/start` — karşılama mesajı
- `/menu` — kategori ve model seçimi
- `/reset` — hafızayı tamamen sıfırla

Bir modelle konuşurken her cevabın altında **💾 Kaydet** ve **🗑️ Hafızayı Temizle** butonları çıkacak.

---

## Yeni Bir Sohbet AI Modeli Eklemek İstersen

1. `config.py` içindeki `PROVIDERS` sözlüğüne yeni bir kayıt ekle (mevcutları örnek al).
2. Eğer o servis OpenAI'nin `/chat/completions` formatını destekliyorsa `adapter_type: "openai_compatible"` yeterli, `providers.py`'da yeni kod yazmana gerek yok.
3. Farklı bir formatsa `providers.py` içine yeni bir `Adapter` sınıfı ekleyip `_ADAPTER_CLASSES` sözlüğüne kaydet.
4. Render'da ilgili API key'i Environment Variables'a ekle.
5. GitHub'a push'la → Render otomatik olarak yeniden deploy eder.

## Sıradaki Aşamalar (2. Faz)

Şu an `/menu` içinde **Görsel Üretimi**, **Ses İşlemleri** ve **Bilgi & Araçlar** kategorileri "yakında" olarak görünüyor. Bunları sırayla ekleyeceğiz:
- 🎨 Görsel: Fal.ai, Pollinations (görsel), JSON2Video
- 🎙️ Ses: AssemblyAI/Deepgram (yazıya çevirme), gTTS (sese çevirme, key gerektirmez)
- 🔍 Araçlar: WolframAlpha, Tavily, hava durumu, döviz kuru vb.

## Sorun Giderme

- **Bot hiç cevap vermiyor**: Render loglarına bak (Render Dashboard → servisin → Logs). `TELEGRAM_BOT_TOKEN` yanlış girilmiş olabilir.
- **Bir model hep hata veriyor**: O servisin API key'i yanlış/eksik olabilir, ya da model adı değişmiş olabilir (AI servisleri model isimlerini zaman zaman günceller).
- **Hafıza kaydolmuyor**: Supabase URL/KEY yanlış girilmiş olabilir, ya da SQL Editor'daki tabloyu oluşturmayı unutmuş olabilirsin (Adım 2).
