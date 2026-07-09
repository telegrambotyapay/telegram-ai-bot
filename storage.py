"""
İki katmanlı hafıza:
1. Oturum hafızası (RAM) - bot çalıştığı sürece her kullanıcının aktif
   konuşması burada tutulur, modele bağlam olarak gönderilir.
2. Kalıcı hafıza (Supabase) - kullanıcı "💾 Kaydet" butonuna bastığında
   oturum geçmişi buraya yazılır ve bot yeniden başlasa bile okunur.
"""
import logging
from typing import List, Dict, Optional

import config

logger = logging.getLogger(__name__)

_sessions: Dict[int, Dict] = {}


def get_session(user_id: int) -> Dict:
    if user_id not in _sessions:
        _sessions[user_id] = {
            "provider": config.DEFAULT_PROVIDER_KEY,
            "transcription_provider": config.DEFAULT_TRANSCRIPTION_KEY,
            "mode": "chat",
            "image_provider": config.DEFAULT_IMAGE_PROVIDER_KEY,
            "active_tool": None,
            "last_analysis": None,
            "history": [],
        }
    return _sessions[user_id]


def set_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["provider"] = provider_key


def set_mode(user_id: int, mode: str) -> None:
    get_session(user_id)["mode"] = mode


def set_image_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["image_provider"] = provider_key


def set_active_tool(user_id: int, tool_key: str) -> None:
    get_session(user_id)["active_tool"] = tool_key


def set_transcription_provider(user_id: int, provider_key: str) -> None:
    get_session(user_id)["transcription_provider"] = provider_key


def append_message(user_id: int, role: str, content: str) -> None:
    session = get_session(user_id)
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-config.MAX_HISTORY_MESSAGES:]


def clear_session_history(user_id: int) -> None:
    get_session(user_id)["history"] = []


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


def clear_all_memory(user_id: int) -> None:
    clear_session_history(user_id)
    clear_cloud_history(user_id)
