"""
Kategorili, çoklu yapay zeka destekli Telegram botu.

Komutlar:
- /start : Karşılama
- /menu  : Kategori menüsü (🤖 Sohbet AI, 🎨 Görsel, 🎙️ Ses, 🔍 Araçlar)
- /reset : Hafızayı temizle (oturum + kalıcı)

Akış:
/menu -> kategori seç -> (sohbet AI için) model seç -> açıklama + onay -> sohbete başla
🔄 Başka bir yapay zekaya yönlendir -> direkt model listesi -> tek tıkla aktif olur.
Bir mesaj hata yüzünden cevaplanamadıysa, model değiştirince o mesaj otomatik
olarak yeni modele sorulur (tekrar yazmaya gerek kalmaz).
Sesli mesajlar otomatik yazıya çevrilip aktif modele sorulur.
Her AI cevabının altında: 💾 Kaydet 🗑️ Temizle 🔊 Sesli Dinle 🔄 Yönlendir butonları.
"""
import os
import logging
import threading
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
        pass  # health check loglarini bastirma


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", config.HEALTH_CHECK_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check sunucusu port {config.HEALTH_CHECK_PORT} üzerinde çalışıyor.")


# ==================== Yardımcı: uzun mesaj gönderme ====================

async def send_long_text(bot, chat_id: int, text: str, reply_markup=None):
    """Telegram'ın 4096 karakter sınırını aşan mesajları parçalara böler."""
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
    ])


def category_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, cat in config.CATEGORIES.items():
        label = cat["label"] if cat["enabled"] else f"{cat['label']} (🚧 yakında)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cat:{key}")])
    return InlineKeyboardMarkup(buttons)


def provider_menu(category_key: str) -> InlineKeyboardMarkup:
    """İlk seçim akışı: tıklanınca açıklama + onay ekranı gelir."""
    cat = config.CATEGORIES[category_key]
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"prov:{p}")]
        for p in cat["providers"]
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def quick_switch_menu(category_key: str) -> InlineKeyboardMarkup:
    """Yönlendirme akışı: tıklanınca açıklama/onay olmadan direkt o modele geçer."""
    cat = config.CATEGORIES[category_key]
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"switchuse:{p}")]
        for p in cat["providers"]
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_menu(provider_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bu modelle sohbete başla", callback_data=f"use:{provider_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:chat")],
    ])


# ==================== Ortak: AI'dan cevap üretip gönderme ====================

async def generate_and_deliver(bot, chat_id: int, user_id: int, user_message: str,
                                context_history: list, provider_key: str):
    """
    Verilen mesaja seçilen sağlayıcıdan cevap üretir ve kullanıcıya gönderir.
    NOT: user_message'ın hafızaya kaydedilmesi bu fonksiyonun DIŞINDA yapılmış olmalı
    (çağıran taraf sorumludur) - burada sadece başarılı cevap hafızaya eklenir.
    """
    try:
        adapter = get_adapter(provider_key)
        reply = adapter.generate(context_history, user_message)
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
            chat_id=chat_id,
            text=f"⚠️ Beklenmeyen bir hata oluştu: {e}",
            reply_markup=switch_button(),
        )
        return

    storage.append_message(user_id, "assistant", reply)
    await send_long_text(bot, chat_id, reply, reply_markup=memory_buttons())


async def activate_provider_and_continue(query, context, provider_key: str):
    """
    Bir modeli aktif eder. Eğer hafızada cevaplanmamış (bir önceki modelin
    hata verdiği) bir kullanıcı mesajı varsa, onu tekrar yazdırmadan otomatik
    olarak yeni modele sorar.
    """
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    storage.set_provider(user_id, provider_key)
    label = config.PROVIDERS[provider_key]["label"]

    session = storage.get_session(user_id)
    history = session["history"]

    pending_message = None
    context_history = history
    if history and history[-1]["role"] == "user":
        pending_message = history[-1]["content"]
        context_history = history[:-1]

    if pending_message:
        await query.edit_message_text(f"✅ Aktif model: {label}\n\nÖnceki mesajını bu modele soruyorum...")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await generate_and_deliver(context.bot, chat_id, user_id, pending_message, context_history, provider_key)
    else:
        await query.edit_message_text(f"✅ Aktif model: {label}\n\nŞimdi bana mesaj yazabilirsin!")


# ==================== Komutlar ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! 👋 Ben çoklu yapay zeka destekli bir Telegram botuyum.\n\n"
        "Kategorileri görmek için /menu yaz.\n"
        "Hafızanı tamamen sıfırlamak için /reset kullanabilirsin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bir kategori seç:", reply_markup=category_menu()
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_all_memory(update.effective_user.id)
    await update.message.reply_text("Hafızan tamamen temizlendi. 🧹")


# ==================== Callback (buton) işleyicileri ====================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:root":
        await query.edit_message_text("Bir kategori seç:", reply_markup=category_menu())
        return

    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat = config.CATEGORIES[cat_key]
        back_only = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")]])

        if not cat["enabled"]:
            await query.edit_message_text(
                f"{cat['label']}\n\n🚧 Bu kategori yakında eklenecek.",
                reply_markup=back_only,
            )
            return

        if cat.get("info_text"):
            await query.edit_message_text(
                f"{cat['label']}\n\n{cat['info_text']}",
                reply_markup=back_only,
            )
            return

        await query.edit_message_text(
            f"{cat['label']}\n{cat['description']}\n\nBir model seç:",
            reply_markup=provider_menu(cat_key),
        )
        return

    if data.startswith("prov:"):
        provider_key = data.split(":", 1)[1]
        info = config.PROVIDERS[provider_key]
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}",
            reply_markup=confirm_menu(provider_key),
        )
        return

    if data.startswith("use:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return

    if data == "mem:save":
        ok = storage.save_history_to_cloud(query.from_user.id)
        msg = "Konuşman kaydedildi. 💾" if ok else (
            "Kaydetme başarısız oldu (Supabase yapılandırılmamış olabilir)."
        )
        await query.answer(text=msg, show_alert=True)
        return

    if data == "mem:clear":
        storage.clear_all_memory(query.from_user.id)
        await query.answer(text="Hafızan temizlendi. 🧹", show_alert=True)
        return

    if data == "switch:menu":
        await query.message.reply_text(
            "Hangi yapay zekaya geçmek istersin?",
            reply_markup=quick_switch_menu("chat"),
        )
        return

    if data.startswith("switchuse:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return

    if data == "tts:speak":
        text_to_speak = query.message.text or ""
        if not text_to_speak.strip():
            return
        chat_id = query.message.chat_id
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        try:
            audio_path = synthesize_speech(text_to_speak)
        except VoiceError as e:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Seslendirme başarısız: {e}")
            return
        try:
            with open(audio_path, "rb") as f:
                await context.bot.send_audio(chat_id=chat_id, audio=f, title="Sesli Cevap")
        finally:
            os.remove(audio_path)
        return


# ==================== Metin mesajları ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)
    provider_key = session["provider"]
    user_message = update.message.text

    # Mesajı hafızaya HEMEN kaydediyoruz (cevap gelmeden önce) — böylece model
    # hata verse bile mesaj kaybolmaz ve model değiştirince otomatik sorulabilir.
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
        transcript = transcribe(bytes(audio_bytes))
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


# ==================== Uygulama başlatma ====================

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı. .env dosyanı kontrol et.")

    start_health_server()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot başlatılıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
"""
Kategorili, çoklu yapay zeka destekli Telegram botu.

Komutlar:
- /start : Karşılama
- /menu  : Kategori menüsü (🤖 Sohbet AI, 🎨 Görsel, 🎙️ Ses, 🔍 Araçlar)
- /reset : Hafızayı temizle (oturum + kalıcı)

Akış:
/menu -> kategori seç -> (sohbet AI için) model seç -> açıklama + onay -> sohbete başla
🔄 Başka bir yapay zekaya yönlendir -> direkt model listesi -> tek tıkla aktif olur.
Bir mesaj hata yüzünden cevaplanamadıysa, model değiştirince o mesaj otomatik
olarak yeni modele sorulur (tekrar yazmaya gerek kalmaz).
Her AI cevabının altında: 💾 Kaydet  🗑️ Hafızayı Temizle  🔄 Yönlendir butonları.
"""
import logging
import threading
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
        pass  # health check loglarini bastirma


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", config.HEALTH_CHECK_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check sunucusu port {config.HEALTH_CHECK_PORT} üzerinde çalışıyor.")


# ==================== Yardımcı: uzun mesaj gönderme ====================

async def send_long_text(bot, chat_id: int, text: str, reply_markup=None):
    """Telegram'ın 4096 karakter sınırını aşan mesajları parçalara böler."""
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
        [InlineKeyboardButton("🔄 Başka bir yapay zekaya yönlendir", callback_data="switch:menu")],
    ])


def category_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, cat in config.CATEGORIES.items():
        label = cat["label"] if cat["enabled"] else f"{cat['label']} (🚧 yakında)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cat:{key}")])
    return InlineKeyboardMarkup(buttons)


def provider_menu(category_key: str) -> InlineKeyboardMarkup:
    """İlk seçim akışı: tıklanınca açıklama + onay ekranı gelir."""
    cat = config.CATEGORIES[category_key]
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"prov:{p}")]
        for p in cat["providers"]
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def quick_switch_menu(category_key: str) -> InlineKeyboardMarkup:
    """Yönlendirme akışı: tıklanınca açıklama/onay olmadan direkt o modele geçer."""
    cat = config.CATEGORIES[category_key]
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"switchuse:{p}")]
        for p in cat["providers"]
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_menu(provider_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bu modelle sohbete başla", callback_data=f"use:{provider_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:chat")],
    ])


# ==================== Ortak: AI'dan cevap üretip gönderme ====================

async def generate_and_deliver(bot, chat_id: int, user_id: int, user_message: str,
                                context_history: list, provider_key: str):
    """
    Verilen mesaja seçilen sağlayıcıdan cevap üretir ve kullanıcıya gönderir.
    NOT: user_message'ın hafızaya kaydedilmesi bu fonksiyonun DIŞINDA yapılmış olmalı
    (çağıran taraf sorumludur) - burada sadece başarılı cevap hafızaya eklenir.
    """
    try:
        adapter = get_adapter(provider_key)
        reply = adapter.generate(context_history, user_message)
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
            chat_id=chat_id,
            text=f"⚠️ Beklenmeyen bir hata oluştu: {e}",
            reply_markup=switch_button(),
        )
        return

    storage.append_message(user_id, "assistant", reply)
    await send_long_text(bot, chat_id, reply, reply_markup=memory_buttons())


async def activate_provider_and_continue(query, context, provider_key: str):
    """
    Bir modeli aktif eder. Eğer hafızada cevaplanmamış (bir önceki modelin
    hata verdiği) bir kullanıcı mesajı varsa, onu tekrar yazdırmadan otomatik
    olarak yeni modele sorar.
    """
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    storage.set_provider(user_id, provider_key)
    label = config.PROVIDERS[provider_key]["label"]

    session = storage.get_session(user_id)
    history = session["history"]

    pending_message = None
    context_history = history
    if history and history[-1]["role"] == "user":
        pending_message = history[-1]["content"]
        context_history = history[:-1]

    if pending_message:
        await query.edit_message_text(f"✅ Aktif model: {label}\n\nÖnceki mesajını bu modele soruyorum...")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await generate_and_deliver(context.bot, chat_id, user_id, pending_message, context_history, provider_key)
    else:
        await query.edit_message_text(f"✅ Aktif model: {label}\n\nŞimdi bana mesaj yazabilirsin!")


# ==================== Komutlar ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! 👋 Ben çoklu yapay zeka destekli bir Telegram botuyum.\n\n"
        "Kategorileri görmek için /menu yaz.\n"
        "Hafızanı tamamen sıfırlamak için /reset kullanabilirsin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bir kategori seç:", reply_markup=category_menu()
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_all_memory(update.effective_user.id)
    await update.message.reply_text("Hafızan tamamen temizlendi. 🧹")


# ==================== Callback (buton) işleyicileri ====================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:root":
        await query.edit_message_text("Bir kategori seç:", reply_markup=category_menu())
        return

    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat = config.CATEGORIES[cat_key]
        if not cat["enabled"]:
            await query.edit_message_text(
                f"{cat['label']}\n\n🚧 Bu kategori yakında eklenecek.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")]]
                ),
            )
            return
        await query.edit_message_text(
            f"{cat['label']}\n{cat['description']}\n\nBir model seç:",
            reply_markup=provider_menu(cat_key),
        )
        return

    if data.startswith("prov:"):
        provider_key = data.split(":", 1)[1]
        info = config.PROVIDERS[provider_key]
        await query.edit_message_text(
            f"{info['label']}\n\n{info['description']}",
            reply_markup=confirm_menu(provider_key),
        )
        return

    if data.startswith("use:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return

    if data == "mem:save":
        ok = storage.save_history_to_cloud(query.from_user.id)
        msg = "Konuşman kaydedildi. 💾" if ok else (
            "Kaydetme başarısız oldu (Supabase yapılandırılmamış olabilir)."
        )
        await query.answer(text=msg, show_alert=True)
        return

    if data == "mem:clear":
        storage.clear_all_memory(query.from_user.id)
        await query.answer(text="Hafızan temizlendi. 🧹", show_alert=True)
        return

    if data == "switch:menu":
        await query.message.reply_text(
            "Hangi yapay zekaya geçmek istersin?",
            reply_markup=quick_switch_menu("chat"),
        )
        return

    if data.startswith("switchuse:"):
        provider_key = data.split(":", 1)[1]
        await activate_provider_and_continue(query, context, provider_key)
        return


# ==================== Metin mesajları ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    session = storage.get_session(user_id)
    provider_key = session["provider"]
    user_message = update.message.text

    # Mesajı hafızaya HEMEN kaydediyoruz (cevap gelmeden önce) — böylece model
    # hata verse bile mesaj kaybolmaz ve model değiştirince otomatik sorulabilir.
    context_history = list(session["history"])
    storage.append_message(user_id, "user", user_message)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await generate_and_deliver(context.bot, chat_id, user_id, user_message, context_history, provider_key)


# ==================== Uygulama başlatma ====================

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı. .env dosyanı kontrol et.")

    start_health_server()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot başlatılıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
