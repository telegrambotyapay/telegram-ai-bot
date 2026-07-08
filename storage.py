"""
İki katmanlı hafıza:
1. Oturum hafızası (RAM) - bot çalıştığı sürece her kullanıcının aktif
   konuşması burada tutulur, modele bağlam olarak gönderilir.
2. Kalıcı hafıza (Supabase) - kullanıcı "💾 Kaydet" butonuna bastığında
   oturum geçmişi buraya yazılır ve bot yeniden başlasa bile okunur.

Supabase ayarlanmamışsa (SUPABASE_URL/KEY boşsa) kalıcı kayıt sessizce
devre dışı kalır, sadece oturum hafızası çalışır.
"""
import logging
from typing import List, Dict, Optional

import config

logger = logging.getLogger(__name__)

# ---------------- Oturum hafızası (RAM) ----------------
# { user_id: {"provider": str, "history": [{"role": ..., "content": ...}]} }
_sessions: Dict[int, Dict] = {}


def get_session(user_id: int) -> Dict:
    if user_id not in _sessions:
        _sessions[user_id] = {
            "provider": config.DEFAULT_PROVIDER_KEY,
            "history": [],
        }
    return _sessions[user_id]


def set_provider(user_id: int, provider_key: str) -> None:
    session = get_session(user_id)
    session["provider"] = provider_key


def append_message(user_id: int, role: str, content: str) -> None:
    session = get_session(user_id)
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-config.MAX_HISTORY_MESSAGES:]


def clear_session_history(user_id: int) -> None:
    session = get_session(user_id)
    session["history"] = []


# ---------------- Kalıcı hafıza (Supabase) ----------------
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
    """Oturumdaki geçmişi Supabase'e kalıcı olarak yazar."""
    client = _get_client()
    if client is None:
        return False
    session = get_session(user_id)
    rows = [
        {
            "user_id": user_id,
            "provider_key": session["provider"],
            "role": msg["role"],
            "content": msg["content"],
        }
        for msg in session["history"]
    ]
    if not rows:
        return False
    try:
        # Önce eskisini temizle, sonra güncel oturumu yaz (basit senkronizasyon)
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
            client.table("conversations")
            .select("role, content")
            .eq("user_id", user_id)
            .order("created_at")
            .execute()
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
