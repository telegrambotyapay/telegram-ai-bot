"""
Kategorili, çoklu yapay zeka destekli Telegram botu.

Komutlar:
- /start : Karşılama
- /menu  : Kategori menüsü (🤖 Sohbet AI, 🎨 Görsel, 🎙️ Ses, 🔍 Araçlar)
- /reset : Hafızayı temizle (oturum + kalıcı)

Akış:
/menu -> kategori seç -> model/servis/araç seç -> açıklama + onay -> kullanmaya başla
🔄 Yönlendir -> tüm kategorilerden direkt seçim -> tek tıkla aktif olur.
Sesli mesajlar otomatik yazıya çevrilip aktif sohbet modeline sorulur.
Fotoğraflar otomatik analiz edilir (Gemini), Word/Excel'e aktarılabilir.
"""
import os
import io
import asyncio
import uuid as uuid_lib
import logging
import threading
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config
import storage
from providers import get_adapter, ProviderError
from voice import transcribe, synthesize_speech, VoiceError
from image_gen import (
    generate_pollinations_image,
    generate_gemini_image,
    generate_agnes_image,
    generate_json2video,
    analyze_image,
    ImageGenError,
)
from document_export import create_docx, create_xlsx, create_pdf
from file_reader import read_file, FileReadError
from astrology import get_horoscope, get_birth_chart, AstrologyError
from tools import (
    get_weather,
    get_exchange_rate,
    ask_wolfram,
    web_search_tavily,
    get_air_quality,
    scan_url_virustotal,
    get_nasa_apod,
    fetch_and_extract_url,
    analyze_face,
    ToolError,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096


# ==================== Health check sunucusu (UptimeRobot için) ====================

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", config.HEALTH_CHECK_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check sunucusu port {config.HEALTH_CHECK_PORT} üzerinde çalışıyor.")


# ==================== Yardımcı: uzun mesaj gönderme ====================

async def send_long_text(bot, chat_id: int, text: str, reply_markup=None):
    if not text:
        text = "(boş cevap alındı)"
    chunks = [text[i:i + TELEGRAM_MESSAGE_LIMIT] for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)]
    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        await bot.send_message(
            chat_id=chat_id, text=chunk, reply_markup=reply_markup if is_last else None
        )


# ==================== Butonlar ====================

def switch_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Başka bir yapay zekaya yönlendir", callback_data="switch:menu")]
    ])


def memory_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 Kaydet", callback_data="mem:save"),
            InlineKeyboardButton("🗑️ Hafızayı Temizle", callback_data="mem:clear"),
        ],
        [
            InlineKeyboardButton("🔊 Sesli Dinle", callback_data="tts:speak"),
            InlineKeyboardButton("🔄 Yönlendir", callback_data="switch:menu"),
        ],
        [
            InlineKeyboardButton("📄 Word'e Aktar", callback_data="export:docx"),
            InlineKeyboardButton("📊 Excel'e Aktar", callback_data="export:xlsx"),
        ],
        [
            InlineKeyboardButton("📕 PDF'e Aktar", callback_data="export:pdf"),
        ],
    ])


def category_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, cat in config.CATEGORIES.items():
        label = cat["label"] if cat["enabled"] else f"{cat['label']} (🚧 yakında)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cat:{key}")])
    buttons.append(
        [InlineKeyboardButton("🧹 Tüm Hafızayı ve Ayarları Sıfırla", callback_data="reset:all")]
    )
    buttons.append([InlineKeyboardButton("❓ Yardım", callback_data="help:show")])
    return InlineKeyboardMarkup(buttons)


def _provider_dict_for_category(category_key: str) -> dict:
    if category_key == "image":
        return config.IMAGE_PROVIDERS
    return config.PROVIDERS  # varsayılan: sohbet AI


def provider_menu(category_key: str) -> InlineKeyboardMarkup:
    """İlk seçim akışı: tıklanınca açıklama + onay ekranı gelir."""
    cat = config.CATEGORIES[category_key]
    pdict = _provider_dict_for_category(category_key)
    buttons = [
        [InlineKeyboardButton(pdict[p]["label"], callback_data=f"prov:{p}")]
        for p in cat["providers"]
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def confirm_menu(provider_key: str, back_category: str = "chat") -> InlineKeyboardMarkup:
    button_text = "✅ Bu modelle sohbete başla" if back_category == "chat" else "✅ Bunu kullan"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button_text, callback_data=f"use:{provider_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data=f"cat:{back_category}")],
    ])


def voice_provider_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(info["label"], callback_data=f"vprov:{key}")]
        for key, info in config.TRANSCRIPTION_PROVIDERS.items()
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def voice_confirm_menu(provider_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bunu kullan", callback_data=f"vuse:{provider_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:voice")],
    ])


def tool_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(info["label"], callback_data=f"tprov:{key}")]
        for key, info in config.TOOL_PROVIDERS.items()
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def tool_confirm_menu(tool_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bunu kullan", callback_data=f"tuse:{tool_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:tools")],
    ])


def astrology_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(info["label"], callback_data=f"aprov:{key}")]
        for key, info in config.ASTROLOGY_FEATURES.items()
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def astrology_confirm_menu(feature_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bunu kullan", callback_data=f"ause:{feature_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:astrology")],
    ])


def combined_switch_menu() -> InlineKeyboardMarkup:
    """Yönlendir butonu: TÜM kategorilerden direkt, onaysız seçim sunar."""
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"switchuse:{p}")]
        for p in config.CATEGORIES["chat"]["providers"]
    ]
    buttons.append([InlineKeyboardButton("── 🐾 Veteriner ──", callback_data="noop")])
    buttons.append(
        [InlineKeyboardButton(config.PROVIDERS["vet_assistant"]["label"], callback_data="switchuse:vet_assistant")]
    )
    buttons.append([InlineKeyboardButton("── 🎨 Görsel/Video ──", callback_data="noop")])
    for p in config.CATEGORIES["image"]["providers"]:
        buttons.append(
            [InlineKeyboardButton(config.IMAGE_PROVIDERS[p]["label"], callback_data=f"switchuse:{p}")]
        )
    buttons.append([InlineKeyboardButton("── 🎙️ Ses Servisi ──", callback_data="noop")])
    for key, info in config.TRANSCRIPTION_PROVIDERS.items():
        buttons.append([InlineKeyboardButton(info["label"], callback_data=f"vswitchuse:{key}")])
    buttons.append([InlineKeyboardButton("── 🔍 Araçlar ──", callback_data="noop")])
    for key, info in config.TOOL_PROVIDERS.items():
        buttons.append([InlineKeyboardButton(info["label"], callback_data=f"tswitchuse:{key}")])
    return InlineKeyboardMarkup(buttons)


# ==================== Ortak: AI'dan cevap üretip gönderme ====================

async def generate_and_deliver(bot, chat_id: int, user_id: int, user_message: str,
                                context_history: list, provider_key: str):
    try:
        adapter = get_adapter(provider_key)
        reply = await asyncio.to_thread(adapter.generate, context_history, user_message)
    except ProviderError as e:
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {config.PROVIDERS[provider_key]['label']} şu an cevap veremedi:\n{e}",
            reply_markup=switch_button(),
        )
        return
    except Exception as e:
        logger.exception("Beklenmeyen hata")
        await bot.send_message(
            chat_id=chat_id, text=f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button()
        )
        return

    storage.append_message(user_id, "assistant", reply)
    storage.get_session(user_id)["last_analysis"] = reply  # Word/Excel'e aktarmak için
    await send_long_text(bot, chat_id, reply, reply_markup=memory_buttons())


async def activate_image_provider(query, provider_key: str):
    user_id = query.from_user.id
    storage.set_mode(user_id, "image")
    storage.set_image_provider(user_id, provider_key)
    info = config.IMAGE_PROVIDERS[provider_key]
    kind_word = "video" if info["kind"] == "video" else "görsel"
    await query.edit_message_text(
        f"✅ Aktif: {info['label']}\n\n"
        f"Şimdi bana ne istediğini anlatan bir mesaj gönder, senin için {kind_word} üreteyim!\n\n"
        f"Sohbete geri dönmek için /menu → 🤖 Sohbet AI'dan bir model seç."
    )


async def activate_tool(query, context, tool_key: str):
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    storage.set_mode(user_id, "tools")
    storage.set_active_tool(user_id, tool_key)
    info = config.TOOL_PROVIDERS[tool_key]

    if tool_key == "nasa":
        await query.edit_message_text(f"✅ {info['label']}\n\nGetiriliyor...")
        try:
            caption, image_url = get_nasa_apod()
            await context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption[:1024])
        except ToolError as e:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {e}")
        return

    await query.edit_message_text(
        f"✅ Aktif araç: {info['label']}\n\n{info['description']}\n\nŞimdi yaz!"
    )


async def activate_provider_and_continue(query, context, provider_key: str):
    """
    Bir modeli aktif eder ve son konuşulan kullanıcı mesajını -- önceden
    cevaplanmış olsa bile -- yeni modele tekrar sorar. Görsel/video
    sağlayıcısıysa görsel moduna geçer.
    """
    if provider_key in config.IMAGE_PROVIDERS:
        await activate_image_provider(query, provider_key)
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    storage.set_provider(user_id, provider_key)
    storage.set_mode(user_id, "chat")
    label = config.PROVIDERS[provider_key]["label"]

    session = storage.get_session(user_id)
    history = session["history"]

    if not history:
        await query.edit_message_text(f"✅ Aktif model: {label}\n\nŞimdi bana mesaj yazabilirsin!")
        return

    if history[-1]["role"] == "user":
        pending_message = history[-1]["content"]
        context_history = history[:-1]
    else:
        last_user_message = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"), None
        )
        if last_user_message is None:
            await query.edit_message_text(f"✅ Aktif model: {label}\n\nŞimdi bana mesaj yazabilirsin!")
            return
        pending_message = last_user_message
        context_history = list(history)
        storage.append_message(user_id, "user", pending_message)

    await query.edit_message_text(f"✅ Aktif model: {label}\n\nSon mesajını bu modele soruyorum...")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await generate_and_deliver(context.bot, chat_id, user_id, pending_message, context_history, provider_key)


# ==================== Komutlar ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! 👋 Ben çoklu yapay zeka destekli bir Telegram botuyum.\n\n"
        "Kategorileri görmek için /menu yaz.\n"
        "Hafızanı tamamen sıfırlamak için /reset kullanabilirsin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bir kategori seç:", reply_markup=category_menu())


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.full_reset(update.effective_user.id)
    await update.message.reply_text("Hafızan ve tüm ayarların (aktif model, mod) varsayılana sıfırlandı. 🧹")


HELP_TEXT = (
    "🤖 *Yapabildiklerim*\n\n"
    "*/menu* — kategori ve model/servis/araç seç\n"
    "*/reset* — hafızayı ve tüm ayarları sıfırla\n"
    "*/hatirlat <SS:DD> <mesaj>* — zamanlı hatırlatma kur (ya da /menu → "
    "⏰ Hatırlatıcı ile adım adım kur)\n"
    "*/help* — bu mesaj\n\n"
    "*Kategoriler:*\n"
    "🤖 Sohbet AI — 9 farklı yapay zeka modeli\n"
    "🐾 Veteriner Asistanı — hayvan sağlığı sorularına genel bilgi\n"
    "🎨 Görsel Üretimi — metinden görsel/video üretimi\n"
    "🎙️ Ses İşlemleri — sesli mesaj ↔ yazı çevirisi\n"
    "🔍 Bilgi & Araçlar — hava durumu, döviz, arama, link özetleme, "
    "yüz analizi ve daha fazlası\n"
    "📁 Dosya İşlemleri — PDF/Word/Excel/CSV okuma ve analiz\n"
    "🔮 Astroloji — burç yorumları ve doğum haritası\n"
    "⏰ Hatırlatıcı — tek seferlik / günlük / haftalık / aylık hatırlatma, "
    "listeleme ve iptal etme\n\n"
    "*Her zaman, hangi modda olursan ol:*\n"
    "🎙️ Sesli mesaj gönderebilirsin (otomatik yazıya çevrilir)\n"
    "📷 Fotoğraf gönderebilirsin (otomatik analiz edilir)\n"
    "📁 Belge gönderebilirsin (otomatik okunup özetlenir)\n\n"
    "Her AI cevabının altında: 💾 Kaydet · 🗑️ Temizle · 🔊 Sesli Dinle · "
    "🔄 Yönlendir · 📄 Word'e Aktar · 📊 Excel'e Aktar · 📕 PDF'e Aktar"
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
WEEKDAY_NAMES_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _parse_clock_time(text: str) -> tuple:
    """'15:04' formatını ayrıştırır, (saat, dakika) döner."""
    text = text.strip()
    try:
        hour_str, minute_str = text.split(":")
        hour, minute = int(hour_str), int(minute_str)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        raise ValueError("format")
    return hour, minute


def reminder_type_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔂 Tek Seferlik", callback_data="remind:once")],
        [InlineKeyboardButton("📆 Her Gün", callback_data="remind:daily")],
        [InlineKeyboardButton("📅 Haftanın Belirli Günü", callback_data="remind:weekly")],
        [InlineKeyboardButton("🗓️ Ayın Belirli Günü", callback_data="remind:monthly")],
        [InlineKeyboardButton("📋 Hatırlatıcılarımı Listele / Sil", callback_data="remind:list")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")],
    ])


def weekday_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"remwd:{i}")]
        for i, name in enumerate(WEEKDAY_NAMES_TR)
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="cat:reminder")])
    return InlineKeyboardMarkup(buttons)


async def show_reminder_list(query, context: ContextTypes.DEFAULT_TYPE, as_new_message: bool = False):
    user_id = query.from_user.id
    prefix = f"rem_{user_id}_"
    jobs = [j for j in context.job_queue.jobs() if j.name and j.name.startswith(prefix) and j.enabled]

    if not jobs:
        text = "📋 Aktif hatırlatıcın yok."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Geri", callback_data="cat:reminder")]])
    else:
        lines = ["📋 Aktif hatırlatıcıların:\n"]
        buttons = []
        for j in jobs:
            display = (j.data or {}).get("display", "?")
            msg = (j.data or {}).get("message", "")
            lines.append(f"• {display}: \"{msg}\"")
            buttons.append([InlineKeyboardButton(f"🗑️ Sil: {display}", callback_data=f"remcancel:{j.name}")])
        buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="cat:reminder")])
        text = "\n".join(lines)
        markup = InlineKeyboardMarkup(buttons)

    if as_new_message:
        await query.message.reply_text(text, reply_markup=markup)
    else:
        await query.edit_message_text(text, reply_markup=markup)


def _schedule_reminder_from_draft(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, draft: dict, message_text: str
) -> str:
    """draft içindeki türe göre uygun job_queue metodunu çağırır, onay metnini döner."""
    job_name = f"rem_{user_id}_{uuid_lib.uuid4().hex[:8]}"
    hour, minute = draft["hour"], draft["minute"]
    rtype = draft["type"]

    async def _send_reminder(ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(chat_id=chat_id, text=f"⏰ Hatırlatma: {message_text}")

    footer = "\n\n📋 /menu → ⏰ Hatırlatıcı → Listele/Sil ile daha sonra iptal edebilirsin."

    if rtype == "once":
        now = datetime.now(ISTANBUL_TZ)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        display = f"Tek seferlik {target.strftime('%d.%m %H:%M')}"
        context.job_queue.run_once(
            _send_reminder, when=target, chat_id=chat_id, name=job_name,
            data={"message": message_text, "display": display},
        )
        day_word = "bugün" if target.date() == now.date() else "yarın"
        return (
            f'⏰ Tamam, {day_word} saat {target.strftime("%H:%M")}\'te hatırlatacağım: '
            f'"{message_text}"\n\nNot: Bot bu süre içinde yeniden başlarsa (deploy) bu hatırlatma kaybolur.'
        )

    time_obj = dt_time(hour=hour, minute=minute, tzinfo=ISTANBUL_TZ)

    if rtype == "daily":
        display = f"Her gün {hour:02d}:{minute:02d}"
        context.job_queue.run_daily(
            _send_reminder, time=time_obj, chat_id=chat_id, name=job_name,
            data={"message": message_text, "display": display},
        )
        return f'⏰ Tamam, her gün saat {hour:02d}:{minute:02d}\'te hatırlatacağım: "{message_text}"{footer}'

    if rtype == "weekly":
        weekday = draft["weekday"]
        display = f"Her {WEEKDAY_NAMES_TR[weekday]} {hour:02d}:{minute:02d}"
        context.job_queue.run_daily(
            _send_reminder, time=time_obj, days=(weekday,), chat_id=chat_id, name=job_name,
            data={"message": message_text, "display": display},
        )
        return (
            f'⏰ Tamam, her {WEEKDAY_NAMES_TR[weekday]} saat {hour:02d}:{minute:02d}\'te '
            f'hatırlatacağım: "{message_text}"{footer}'
        )

    if rtype == "monthly":
        monthday = draft["monthday"]
        display = f"Her ayın {monthday}. günü {hour:02d}:{minute:02d}"
        context.job_queue.run_monthly(
            _send_reminder, when=time_obj, day=monthday, chat_id=chat_id, name=job_name,
            day_is_strict=False,
            data={"message": message_text, "display": display},
        )
        return (
            f'⏰ Tamam, her ayın {monthday}. günü saat {hour:02d}:{minute:02d}\'te '
            f'hatırlatacağım: "{message_text}"{footer}'
        )

    return "⚠️ Bilinmeyen hatırlatıcı türü."


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Kullanım: /hatirlat <SS:DD> <mesaj>\nÖrnek: /hatirlat 15:04 Sütü ocaktan al\n\n"
            "Tekrarlayan (her gün/hafta/ay) hatırlatıcılar için /menu → ⏰ Hatırlatıcı kullan."
        )
        return
    try:
        hour, minute = _parse_clock_time(args[0])
    except ValueError:
        await update.message.reply_text(
            "İlk parametre SS:DD formatında bir saat olmalı. Örn: /hatirlat 15:04 Toplantı var"
        )
        return

    message_text = " ".join(args[1:])
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if context.job_queue is None:
        await update.message.reply_text(
            "⚠️ Hatırlatıcı özelliği için sunucuda job-queue bileşeni kurulu değil."
        )
        return

    draft = {"type": "once", "hour": hour, "minute": minute}
    confirmation = _schedule_reminder_from_draft(context, chat_id, user_id, draft, message_text)
    await update.message.reply_text(confirmation)


# ==================== Callback (buton) işleyicileri ====================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:root":
        await query.edit_message_text("Bir kategori seç:", reply_markup=category_menu())
        return

    if data == "reset:all":
        storage.full_reset(query.from_user.id)
        await query.edit_message_text(
            "🧹 Her şey sıfırlandı! Hafıza temizlendi, tüm yapay zekalar/araçlar "
            "varsayılana döndü.\n\nBir kategori seç:",
            reply_markup=category_menu(),
        )
        return

    if data == "help:show":
        await query.message.reply_text(HELP_TEXT, parse_mode="Markdown")
        return

    if data in ("remind:once", "remind:daily"):
        if context.job_queue is None:
            await query.edit_message_text("⚠️ Hatırlatıcı özelliği için sunucuda job-queue bileşeni kurulu değil.")
            return
        user_id = query.from_user.id
        rtype = "once" if data == "remind:once" else "daily"
        storage.get_session(user_id)["reminder_draft"] = {"type": rtype}
        storage.set_mode(user_id, "reminder_time")
        hint = "Eğer o saat bugün geçtiyse, yarın hatırlatırım.\n\n" if rtype == "once" else ""
        await query.edit_message_text(
            f"⏰ Saat kaçta hatırlatayım? SS:DD formatında yaz (örn. 15:04).\n{hint}"
            "İptal etmek için /menu yazabilirsin."
        )
        return

    if data == "remind:weekly":
        if context.job_queue is None:
            await query.edit_message_text("⚠️ Hatırlatıcı özelliği için sunucuda job-queue bileşeni kurulu değil.")
            return
        await query.edit_message_text("📅 Haftanın hangi günü?", reply_markup=weekday_menu())
        return

    if data.startswith("remwd:"):
        weekday = int(data.split(":", 1)[1])
        user_id = query.from_user.id
        storage.get_session(user_id)["reminder_draft"] = {"type": "weekly", "weekday": weekday}
        storage.set_mode(user_id, "reminder_time")
        await query.edit_message_text(
            f"⏰ Her {WEEKDAY_NAMES_TR[weekday]} saat kaçta hatırlatayım? "
            f"SS:DD formatında yaz (örn. 09:00)."
        )
        return

    if data == "remind:monthly":
        if context.job_queue is None:
            await query.edit_message_text("⚠️ Hatırlatıcı özelliği için sunucuda job-queue bileşeni kurulu değil.")
            return
        user_id = query.from_user.id
        storage.get_session(user_id)["reminder_draft"] = {"type": "monthly"}
        storage.set_mode(user_id, "reminder_pick_monthday")
        await query.edit_message_text("🗓️ Ayın kaçıncı günü? Bir sayı yaz (1-31).")
        return

    if data == "remind:list":
        await show_reminder_list(query, context)
        return

    if data.startswith("remcancel:"):
        job_name = data.split(":", 1)[1]
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for j in jobs:
            j.schedule_removal()
        await query.answer(text="🗑️ Hatırlatıcı silindi.", show_alert=True)
        await show_reminder_list(query, context)
        return
        return

    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat = config.CATEGORIES[cat_key]
        back_only = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")]])

        if not cat["enabled"]:
            await query.edit_message_text(
                f"{cat['label']}\n\n🚧 Bu kategori yakında eklenecek.", reply_markup=back_only
            )
            return

        if len(cat["providers"]) == 1 and not cat.get("info_text"):
            # Tek seçenekli kategori: liste adımını atla, direkt açıklama + onay göster.
            only_key = cat["providers"][0]
            pdict = _provider_dict_for_category(cat_key)
            info = pdict[only_key]
            single_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Bu modelle sohbete başla", callback_data=f"use:{only_key}")],
                [InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")],
            ])
            await query.edit_message_text(f"{info['label']}\n\n{info['description']}", reply_markup=single_markup)
            return

        if cat.get("info_text"):
            if cat_key == "voice":
                extra_markup = voice_provider_menu()
            elif cat_key == "image":
                extra_markup = provider_menu("image")
            elif cat_key == "tools":
                extra_markup = tool_menu()
            elif cat_key == "astrology":
                extra_markup = astrology_menu()
            elif cat_key == "reminder":
                extra_markup = reminder_type_menu()
            else:
                extra_markup = back_only
            await query.edit_message_text(f"{cat['label']}\n\n{cat['info_text']}", reply_markup=extra_markup)
            return

        await query.edit_message_text(
            f"{cat['label']}\n{cat['description']}\n\nBir model seç:", reply_markup=provider_menu(cat_key)
        )
        return

    if data.startswith("prov:"):
        provider_key = data.split(":", 1)[1]
        if provider_key in config.PROVIDERS:
            info = config.PROVIDERS[provider_key]
            back_cat = "chat"
        else:
            info = config.IMAGE_PROVIDERS[provider_key]
            back_cat = "image"
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}", reply_markup=confirm_menu(provider_key, back_cat)
        )
        return

    if data.startswith("use:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return

    if data == "mem:save":
        ok = storage.save_history_to_cloud(query.from_user.id)
        msg = "Konuşman kaydedildi. 💾" if ok else "Kaydetme başarısız oldu (Supabase yapılandırılmamış olabilir)."
        await query.answer(text=msg, show_alert=True)
        return

    if data == "mem:clear":
        storage.clear_all_memory(query.from_user.id)
        await query.answer(text="Hafızan temizlendi. 🧹", show_alert=True)
        return

    if data == "switch:menu":
        await query.message.reply_text("Ne değiştirmek istersin?", reply_markup=combined_switch_menu())
        return

    if data == "noop":
        return

    if data.startswith("vswitchuse:"):
        provider_key = data.split(":", 1)[1]
        storage.set_transcription_provider(query.from_user.id, provider_key)
        label = config.TRANSCRIPTION_PROVIDERS[provider_key]["label"]
        await query.edit_message_text(f"✅ Sesli mesajlar artık şununla çevrilecek: {label}")
        return

    if data.startswith("switchuse:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return

    if data.startswith("tswitchuse:"):
        tool_key = data.split(":", 1)[1]
        await activate_tool(query, context, tool_key)
        return

    if data.startswith("vprov:"):
        provider_key = data.split(":", 1)[1]
        info = config.TRANSCRIPTION_PROVIDERS[provider_key]
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}", reply_markup=voice_confirm_menu(provider_key)
        )
        return

    if data.startswith("vuse:"):
        provider_key = data.split(":", 1)[1]
        storage.set_transcription_provider(query.from_user.id, provider_key)
        label = config.TRANSCRIPTION_PROVIDERS[provider_key]["label"]
        await query.edit_message_text(f"✅ Sesli mesajlar artık şununla çevrilecek: {label}")
        return

    if data.startswith("tprov:"):
        tool_key = data.split(":", 1)[1]
        info = config.TOOL_PROVIDERS[tool_key]
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}", reply_markup=tool_confirm_menu(tool_key)
        )
        return

    if data.startswith("tuse:"):
        tool_key = data.split(":", 1)[1]
        await activate_tool(query, context, tool_key)
        return

    if data.startswith("aprov:"):
        feature_key = data.split(":", 1)[1]
        info = config.ASTROLOGY_FEATURES[feature_key]
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}",
            reply_markup=astrology_confirm_menu(feature_key),
        )
        return

    if data.startswith("ause:"):
        feature_key = data.split(":", 1)[1]
        user_id = query.from_user.id
        storage.set_mode(user_id, "astrology")
        storage.set_active_astrology_feature(user_id, feature_key)
        info = config.ASTROLOGY_FEATURES[feature_key]
        await query.edit_message_text(f"✅ Aktif: {info['label']}\n\n{info['description']}")
        return

    if data == "tts:speak":
        text_to_speak = query.message.text or ""
        if not text_to_speak.strip():
            return
        chat_id = query.message.chat_id
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        try:
            audio_path = await asyncio.to_thread(synthesize_speech, text_to_speak)
        except VoiceError as e:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Seslendirme başarısız: {e}")
            return
        try:
            with open(audio_path, "rb") as f:
                await context.bot.send_audio(chat_id=chat_id, audio=f, title="Sesli Cevap")
        finally:
            os.remove(audio_path)
        return

    if data in ("export:docx", "export:xlsx", "export:pdf"):
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        session = storage.get_session(user_id)
        analysis = session.get("last_analysis")
        if not analysis:
            await query.answer(text="Aktarılacak bir analiz bulunamadı.", show_alert=True)
            return
        try:
            if data == "export:docx":
                file_path = await asyncio.to_thread(create_docx, "AI Çıktısı", analysis)
            elif data == "export:xlsx":
                file_path = await asyncio.to_thread(create_xlsx, "AI Çıktısı", analysis)
            else:
                file_path = await asyncio.to_thread(create_pdf, "AI Çıktısı", analysis)
        except Exception as e:
            logger.exception("Dosya oluşturma hatası")
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Dosya oluşturulamadı: {e}")
            return
        try:
            with open(file_path, "rb") as f:
                await context.bot.send_document(chat_id=chat_id, document=f)
        finally:
            os.remove(file_path)
        return


# ==================== Fotoğraf mesajları (görsel analizi) ====================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)

    # Yüz Analizi aracı aktifse, Gemini yerine Face++ kullan
    if session.get("mode") == "tools" and session.get("active_tool") == "face_analysis":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())
        try:
            result = await asyncio.to_thread(analyze_face, image_bytes)
        except ToolError as e:
            await update.message.reply_text(f"⚠️ {e}", reply_markup=switch_button())
            return
        except Exception as e:
            logger.exception("Yüz analizinde beklenmeyen hata")
            await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button())
            return
        await update.message.reply_text(result, reply_markup=switch_button())
        return

    if not config.GROQ_API_KEY and not config.GOOGLE_AI_STUDIO_API_KEY:
        await update.message.reply_text(
            "⚠️ Görsel analizi için GROQ_API_KEY ya da GOOGLE_AI_STUDIO_API_KEY tanımlı olmalı."
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())
    caption = update.message.caption

    try:
        analysis = await asyncio.to_thread(analyze_image, image_bytes, instruction=caption)
    except ImageGenError as e:
        await update.message.reply_text(f"⚠️ Görsel analiz edilemedi:\n{e}")
        return
    except Exception as e:
        logger.exception("Görsel analizinde beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}")
        return

    session = storage.get_session(user_id)
    session["last_analysis"] = analysis

    await send_long_text(context.bot, chat_id, f"🔍 {analysis}", reply_markup=memory_buttons())


# ==================== Belge dosyaları (PDF/Word/Excel/CSV/TXT) ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)

    doc = update.message.document
    filename = doc.file_name or "dosya"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    doc_file = await doc.get_file()
    file_bytes = bytes(await doc_file.download_as_bytearray())

    try:
        content = await asyncio.to_thread(read_file, filename, file_bytes)
    except FileReadError as e:
        await update.message.reply_text(f"⚠️ Dosya okunamadı:\n{e}")
        return
    except Exception as e:
        logger.exception("Dosya okumada beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}")
        return

    truncated = len(content) > 6000
    content_for_ai = content[:6000]

    caption = update.message.caption
    instruction = caption or (
        f"Bu, kullanıcının yüklediği '{filename}' adlı dosyanın içeriğidir. "
        "İçeriği özetle, önemli noktaları/verileri belirt. Eğer tablo/liste "
        "gibi yapılandırılmış veri varsa, düzenli satırlar halinde, mümkünse "
        "sütunları '|' işaretiyle ayırarak göster."
    )
    prompt = f"{instruction}\n\n--- DOSYA İÇERİĞİ ({filename}) ---\n{content_for_ai}"
    if truncated:
        prompt += "\n\n(Not: dosya uzun olduğu için sadece ilk kısmı işlendi.)"

    provider_key = session["provider"]
    context_history = list(session["history"])
    storage.append_message(user_id, "user", f"[📁 Dosya gönderildi: {filename}]")

    await generate_and_deliver(context.bot, chat_id, user_id, prompt, context_history, provider_key)


# ==================== Astroloji mesajları ====================

async def handle_astrology_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, text: str):
    chat_id = update.effective_chat.id
    feature_key = session.get("active_astrology_feature")

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        if feature_key in ("daily", "weekly", "monthly", "yearly"):
            result = await asyncio.to_thread(get_horoscope, text, feature_key)
        elif feature_key == "birthchart":
            result = await asyncio.to_thread(get_birth_chart, text)
        else:
            await update.message.reply_text("⚠️ Bilinmeyen astroloji özelliği, /menu ile tekrar seç.")
            return
    except AstrologyError as e:
        await update.message.reply_text(f"⚠️ {e}", reply_markup=switch_button())
        return
    except Exception as e:
        logger.exception("Astroloji özelliğinde beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button())
        return

    await send_long_text(context.bot, chat_id, result, reply_markup=switch_button())


# ==================== Araç mesajları ====================

async def handle_tool_message(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, text: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    tool_key = session.get("active_tool")

    if tool_key == "face_analysis":
        await update.message.reply_text(
            "😀 Bu araç fotoğraf bekliyor — lütfen bir FOTOĞRAF gönder (metin değil)."
        )
        return

    if tool_key == "link_summary":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            content = await asyncio.to_thread(fetch_and_extract_url, text)
        except ToolError as e:
            await update.message.reply_text(f"⚠️ {e}", reply_markup=switch_button())
            return
        except Exception as e:
            logger.exception("Link özetlemede beklenmeyen hata")
            await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button())
            return

        prompt = (
            f"Aşağıda bir web sayfasından ({text}) çekilen içerik var. Bunu özetle, "
            f"önemli noktaları belirt:\n\n{content}"
        )
        provider_key = session["provider"]
        context_history = list(session["history"])
        storage.append_message(user_id, "user", f"[🔗 Link özetleniyor: {text}]")
        await generate_and_deliver(context.bot, chat_id, user_id, prompt, context_history, provider_key)
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        if tool_key == "weather":
            result = await asyncio.to_thread(get_weather, text)
        elif tool_key == "exchange":
            result = await asyncio.to_thread(get_exchange_rate, text)
        elif tool_key == "wolfram":
            result = await asyncio.to_thread(ask_wolfram, text)
        elif tool_key == "search":
            result = await asyncio.to_thread(web_search_tavily, text)
        elif tool_key == "air":
            result = await asyncio.to_thread(get_air_quality, text)
        elif tool_key == "virustotal":
            result = await asyncio.to_thread(scan_url_virustotal, text)
        else:
            await update.message.reply_text("⚠️ Bilinmeyen araç, /menu ile tekrar seç.")
            return
    except ToolError as e:
        await update.message.reply_text(f"⚠️ {e}", reply_markup=switch_button())
        return
    except Exception as e:
        logger.exception("Araç kullanımında beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button())
        return

    await update.message.reply_text(result, reply_markup=switch_button())


# ==================== Metin mesajları ====================

async def handle_image_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, prompt: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    provider_key = session.get("image_provider", config.DEFAULT_IMAGE_PROVIDER_KEY)
    info = config.IMAGE_PROVIDERS[provider_key]

    action = "record_video" if info["kind"] == "video" else "upload_photo"
    await context.bot.send_chat_action(chat_id=chat_id, action=action)

    try:
        if provider_key == "pollinations_image":
            content = await asyncio.to_thread(generate_pollinations_image, prompt)
        elif provider_key == "gemini_image":
            content = await asyncio.to_thread(generate_gemini_image, prompt)
        elif provider_key == "agnes_image":
            content = await asyncio.to_thread(generate_agnes_image, prompt)
        elif provider_key == "json2video":
            content = await asyncio.to_thread(generate_json2video, prompt)
        else:
            raise ImageGenError("Bilinmeyen görsel/video sağlayıcı.")
    except ImageGenError as e:
        await update.message.reply_text(f"⚠️ {info['label']} üretemedi:\n{e}", reply_markup=switch_button())
        return
    except Exception as e:
        logger.exception("Görsel/video üretiminde beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}", reply_markup=switch_button())
        return

    caption = prompt[:200]
    bio = io.BytesIO(content)
    if info["kind"] == "video":
        bio.name = "video.mp4"
        await context.bot.send_video(chat_id=chat_id, video=bio, caption=f"🎬 {caption}")
    else:
        bio.name = "image.jpg"
        await context.bot.send_photo(chat_id=chat_id, photo=bio, caption=f"🎨 {caption}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)
    user_message = update.message.text

    mode = session.get("mode", "chat")
    if mode == "image":
        await handle_image_prompt(update, context, session, user_message)
        return
    if mode == "tools":
        await handle_tool_message(update, context, session, user_message)
        return
    if mode == "astrology":
        await handle_astrology_message(update, context, session, user_message)
        return
    if mode == "reminder_pick_monthday":
        try:
            monthday = int(user_message.strip())
            if not (1 <= monthday <= 31):
                raise ValueError
        except ValueError:
            await update.message.reply_text("Bunu ayın günü olarak anlayamadım. 1-31 arası bir sayı yaz.")
            return
        draft = session.get("reminder_draft") or {"type": "monthly"}
        draft["monthday"] = monthday
        session["reminder_draft"] = draft
        storage.set_mode(user_id, "reminder_time")
        await update.message.reply_text(
            f"⏰ Her ayın {monthday}. günü saat kaçta hatırlatayım? SS:DD formatında yaz (örn. 09:00)."
        )
        return
    if mode == "reminder_time":
        try:
            hour, minute = _parse_clock_time(user_message)
        except ValueError:
            await update.message.reply_text(
                "Bunu bir saat olarak anlayamadım. SS:DD formatında yaz, örn: 15:04. Tekrar yazar mısın?"
            )
            return
        draft = session.get("reminder_draft") or {"type": "once"}
        draft["hour"] = hour
        draft["minute"] = minute
        session["reminder_draft"] = draft
        storage.set_mode(user_id, "reminder_message")
        await update.message.reply_text("⏰ Tamam. Şimdi ne hatırlatmamı istersin? Mesajını yaz.")
        return
    if mode == "reminder_message":
        draft = session.get("reminder_draft")
        if not draft:
            storage.set_mode(user_id, "chat")
            await update.message.reply_text("⚠️ Bir şeyler ters gitti, /menu → ⏰ Hatırlatıcı ile tekrar dene.")
            return
        if context.job_queue is None:
            storage.set_mode(user_id, "chat")
            await update.message.reply_text("⚠️ Hatırlatıcı özelliği için sunucuda job-queue bileşeni kurulu değil.")
            return
        confirmation = _schedule_reminder_from_draft(context, chat_id, user_id, draft, user_message)
        session["reminder_draft"] = None
        storage.set_mode(user_id, "chat")
        await update.message.reply_text(confirmation)
        return

    provider_key = session["provider"]
    context_history = list(session["history"])
    storage.append_message(user_id, "user", user_message)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await generate_and_deliver(context.bot, chat_id, user_id, user_message, context_history, provider_key)


# ==================== Sesli mesajlar ====================

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)
    provider_key = session["provider"]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    voice_file = await update.message.voice.get_file()
    audio_bytes = await voice_file.download_as_bytearray()

    try:
        transcript = await asyncio.to_thread(
            transcribe, bytes(audio_bytes), preferred=session.get("transcription_provider", "auto")
        )
    except VoiceError as e:
        await update.message.reply_text(f"⚠️ Sesli mesaj çözümlenemedi:\n{e}")
        return
    except Exception as e:
        logger.exception("Ses transkripsiyon hatası")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}")
        return

    if not transcript.strip():
        await update.message.reply_text("⚠️ Sesli mesajda anlaşılır bir konuşma bulamadım.")
        return

    await update.message.reply_text(f'🎙️ Anladığım: "{transcript}"')

    context_history = list(session["history"])
    storage.append_message(user_id, "user", transcript)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await generate_and_deliver(context.bot, chat_id, user_id, transcript, context_history, provider_key)


# ==================== Genel hata koruması ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Beklenmeyen hata: {context.error}", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "⚠️ Beklenmeyen bir hata oluştu. Tekrar dener misin? "
                    "Sorun devam ederse başka bir yapay zekaya geçebilirsin."
                ),
                reply_markup=switch_button(),
            )
    except Exception:
        logger.exception("Hata mesajı gönderilirken de hata oluştu")


# ==================== Uygulama başlatma ====================

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı. .env dosyanı kontrol et.")

    start_health_server()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("hatirlat", remind_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("Bot başlatılıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
