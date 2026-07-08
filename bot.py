"""
Kategorili, çoklu yapay zeka destekli Telegram botu.

Komutlar:
- /start : Karşılama
- /menu  : Kategori menüsü (🤖 Sohbet AI, 🎨 Görsel, 🎙️ Ses, 🔍 Araçlar)
- /reset : Hafızayı temizle (oturum + kalıcı)

Akış:
/menu -> kategori seç -> (sohbet AI için) model seç -> açıklama + onay -> sohbete başla
Her AI cevabının altında: 💾 Kaydet  🗑️ Hafızayı Temizle butonları.
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
from telegram.constants import ParseMode

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

    def log_message(self, format, *args):
        pass  # health check loglarini bastirma


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", config.HEALTH_CHECK_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check sunucusu port {config.HEALTH_CHECK_PORT} üzerinde çalışıyor.")


# ==================== Yardımcılar ====================

async def send_long_message(update: Update, text: str, reply_markup=None):
    """Telegram'ın 4096 karakter sınırını aşan mesajları parçalara böler."""
    if not text:
        text = "(boş cevap alındı)"
    chunks = [text[i:i + TELEGRAM_MESSAGE_LIMIT] for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)]
    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        await update.effective_message.reply_text(
            chunk, reply_markup=reply_markup if is_last else None
        )


def memory_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 Kaydet", callback_data="mem:save"),
            InlineKeyboardButton("🗑️ Hafızayı Temizle", callback_data="mem:clear"),
        ]
    ])


def category_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, cat in config.CATEGORIES.items():
        label = cat["label"] if cat["enabled"] else f"{cat['label']} (🚧 yakında)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cat:{key}")])
    return InlineKeyboardMarkup(buttons)


def provider_menu(category_key: str) -> InlineKeyboardMarkup:
    cat = config.CATEGORIES[category_key]
    buttons = [
        [InlineKeyboardButton(config.PROVIDERS[p]["label"], callback_data=f"prov:{p}")]
        for p in cat["providers"]
    ]
    buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="menu:root")])
    return InlineKeyboardMarkup(buttons)


def confirm_menu(provider_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bu modelle sohbete başla", callback_data=f"use:{provider_key}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="cat:chat")],
    ])


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
        storage.set_provider(query.from_user.id, provider_key)
        label = config.PROVIDERS[provider_key]["label"]
        await query.edit_message_text(
            f"✅ Aktif model: {label}\n\nŞimdi bana mesaj yazabilirsin!"
        )
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


# ==================== Metin mesajları ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = storage.get_session(user_id)
    provider_key = session["provider"]
    user_message = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        adapter = get_adapter(provider_key)
        reply = adapter.generate(session["history"], user_message)
    except ProviderError as e:
        await update.message.reply_text(
            f"⚠️ {config.PROVIDERS[provider_key]['label']} şu an cevap veremedi:\n{e}\n\n"
            "Başka bir model denemek için /menu yazabilirsin."
        )
        return
    except Exception as e:
        logger.exception("Beklenmeyen hata")
        await update.message.reply_text(f"⚠️ Beklenmeyen bir hata oluştu: {e}")
        return

    storage.append_message(user_id, "user", user_message)
    storage.append_message(user_id, "assistant", reply)

    await send_long_message(update, reply, reply_markup=memory_buttons())


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
