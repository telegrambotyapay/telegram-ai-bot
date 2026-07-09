"""
İki katmanlı hafıza:
1. Oturum hafızası (RAM) - bot çalıştığı sürece her kullanıcının aktif
   konuşması burada tutulur, modele bağlam olarak gönderilir.
2. Kalıcı hafıza (Supabase) - konuşma geçmişi kullanıcı "💾 Kaydet" butonuna
   bastığında kaydedilir; hangi model/mod/araç aktif olduğu gibi AYARLAR ise
   her değiştiğinde OTOMATİK olarak kaydedilir, böylece Render yeniden
   başlasa (deploy) bile kaldığın yerden devam edersin.
"""
import logging
from typing import List, Dict, Optional

import config

logger = logging.getLogger(__name__)

_sessions: Dict[int, Dict] = {}

_DEFAULTS = {
    "provider": lambda: config.DEFAULT_PROVIDER_KEY,
    "transcription_provider": lambda: config.DEFAULT_TRANSCRIPTION_KEY,
    "mode": lambda: "chat",
    "image_provider": lambda: config.DEFAULT_IMAGE_PROVIDER_KEY,
    "active_tool": lambda: None,
    "active_astrology_feature": lambda: None,
}


def get_session(user_id: int) -> Dict:
    if user_id not in _sessions:
        session = {key: default() for key, default in _DEFAULTS.items()}
        session["last_analysis"] = None
        session["reminder_pending_time"] = None
        session["reminder_draft"] = None
        session["history"] = []

        saved = _load_settings(user_id)
        if saved:
            for key in _DEFAULTS:
                if saved.get(key) is not None:
                    session[key] = saved[key]

        _sessions[user_id] = session
    return _sessions[user_id]


def set_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["provider"] = provider_key
    _persist_settings(user_id)


def set_mode(user_id: int, mode: str) -> None:
    get_session(user_id)["mode"] = mode
    _persist_settings(user_id)


def set_image_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["image_provider"] = provider_key
    _persist_settings(user_id)


def set_active_tool(user_id: int, tool_key: str) -> None:
    get_session(user_id)["active_tool"] = tool_key
    _persist_settings(user_id)


def set_active_astrology_feature(user_id: int, feature_key: str) -> None:
    get_session(user_id)["active_astrology_feature"] = feature_key
    _persist_settings(user_id)


def set_transcription_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["transcription_provider"] = provider_key
    _persist_settings(user_id)


def append_message(user_id: int, role: str, content: str) -> None:
    session = get_session(user_id)
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-config.MAX_HISTORY_MESSAGES:]


def clear_session_history(user_id: int) -> None:
    get_session(user_id)["history"] = []


# ---------------- Supabase ----------------
_supabase_client = None
_supabase_checked = False


def _get_client():
    global _supabase_client, _supabase_checked
    if _supabase_checked:
        return _supabase_client
    _supabase_checked = True
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        logger.warning("Supabase yapılandırılmamış, kalıcı hafıza devre dışı.")
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    except Exception:
        logger.exception("Supabase istemcisi oluşturulamadı.")
        _supabase_client = None
    return _supabase_client


def save_history_to_cloud(user_id: int) -> bool:
    client = _get_client()
    if client is None:
        return False
    session = get_session(user_id)
    rows = [
        {"user_id": user_id, "provider_key": session["provider"], "role": m["role"], "content": m["content"]}
        for m in session["history"]
    ]
    if not rows:
        return False
    try:
        client.table("conversations").delete().eq("user_id", user_id).execute()
        client.table("conversations").insert(rows).execute()
        return True
    except Exception:
        logger.exception("Supabase'e kayıt sırasında hata")
        return False


def load_history_from_cloud(user_id: int) -> Optional[List[Dict[str, str]]]:
    client = _get_client()
    if client is None:
        return None
    try:
        result = (
            client.table("conversations").select("role, content").eq("user_id", user_id).order("created_at").execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in result.data]
    except Exception:
        logger.exception("Supabase'den okuma sırasında hata")
        return None


def clear_cloud_history(user_id: int) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.table("conversations").delete().eq("user_id", user_id).execute()
        return True
    except Exception:
        logger.exception("Supabase'de silme sırasında hata")
        return False


def _persist_settings(user_id: int) -> None:
    """Aktif model/mod/araç seçimlerini Supabase'e yazar (deploy sonrası hafıza için)."""
    client = _get_client()
    if client is None:
        return
    session = _sessions.get(user_id)
    if session is None:
        return
    try:
        client.table("user_settings").upsert({
            "user_id": user_id,
            "provider": session["provider"],
            "transcription_provider": session["transcription_provider"],
            "mode": session["mode"],
            "image_provider": session["image_provider"],
            "active_tool": session["active_tool"],
            "active_astrology_feature": session["active_astrology_feature"],
        }).execute()
    except Exception:
        logger.exception("Ayarlar Supabase'e kaydedilirken hata")


def _load_settings(user_id: int) -> Optional[dict]:
    client = _get_client()
    if client is None:
        return None
    try:
        result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]
    except Exception:
        logger.exception("Ayarlar Supabase'den okunurken hata")
    return None


def clear_all_memory(user_id: int) -> None:
    clear_session_history(user_id)
    clear_cloud_history(user_id)


def full_reset(user_id: int) -> None:
    """Hafızayı VE tüm seçili mod/sağlayıcı tercihlerini varsayılana sıfırlar."""
    clear_all_memory(user_id)
    session = get_session(user_id)
    session["provider"] = config.DEFAULT_PROVIDER_KEY
    session["transcription_provider"] = config.DEFAULT_TRANSCRIPTION_KEY
    session["mode"] = "chat"
    session["image_provider"] = config.DEFAULT_IMAGE_PROVIDER_KEY
    session["active_tool"] = None
    session["active_astrology_feature"] = None
    session["last_analysis"] = None
    _persist_settings(user_id)
