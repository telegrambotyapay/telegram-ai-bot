"""
Astroloji özellikleri:
- get_horoscope(): günlük/haftalık/aylık/yıllık burç yorumu (Gemini ile üretilir)
- get_birth_chart(): doğum haritası + AI yorumu (freeastrologyapi.com + Gemini)
"""
import time
import logging

import requests

import config
from providers import get_adapter, ProviderError

logger = logging.getLogger(__name__)


class AstrologyError(Exception):
    """Astroloji isteği başarısız olduğunda fırlatılır."""


def _post_with_retry(url: str, headers: dict, payload: dict, timeout: int, label: str) -> dict:
    """429 (rate limit) durumunda birkaç kez tekrar dener."""
    last_error = None
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 429:
            last_error = "429 Too Many Requests"
            logger.warning(f"{label} rate limit, {attempt + 1}. deneme...")
            time.sleep(3 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    raise AstrologyError(f"{label} şu an çok yoğun (rate limit). Birkaç dakika sonra tekrar dene. ({last_error})")


ZODIAC_TR_TO_EN = {
    "koç": "aries", "koc": "aries",
    "boğa": "taurus", "boga": "taurus",
    "ikizler": "gemini",
    "yengeç": "cancer", "yengec": "cancer",
    "aslan": "leo",
    "başak": "virgo", "basak": "virgo",
    "terazi": "libra",
    "akrep": "scorpio",
    "yay": "sagittarius",
    "oğlak": "capricorn", "oglak": "capricorn",
    "kova": "aquarius",
    "balık": "pisces", "balik": "pisces",
}


def _normalize_sign(sign_text: str) -> str:
    key = sign_text.strip().lower()
    if key in ZODIAC_TR_TO_EN:
        return ZODIAC_TR_TO_EN[key]
    if key in set(ZODIAC_TR_TO_EN.values()):
        return key
    raise AstrologyError(
        "Burcunu anlayamadım. Şunlardan birini yaz: Koç, Boğa, İkizler, Yengeç, "
        "Aslan, Başak, Terazi, Akrep, Yay, Oğlak, Kova, Balık"
    )


def get_horoscope(sign_text: str, period: str) -> str:
    """
    period: 'daily', 'weekly', 'monthly' ya da 'yearly'
    Not: astrology-api.io'nun burç yorumu endpoint'i defalarca denenmesine
    rağmen güvenilir şekilde bulunamadı (dokümantasyonu genel aramada net
    değil). Bunun yerine, zaten kanıtlanmış çalışan Gemini altyapımızı
    kullanarak doğrudan bir yorum üretiyoruz - garantili çalışır.
    """
    sign = _normalize_sign(sign_text)
    period_tr = {
        "daily": "günlük", "weekly": "haftalık",
        "monthly": "aylık", "yearly": "yıllık",
    }.get(period, period)

    prompt = (
        f"{sign.capitalize()} burcu için {period_tr} bir burç yorumu yaz. "
        f"Türkçe, sıcak, akıcı bir üslupla; aşk, kariyer/iş ve genel enerji "
        f"hakkında birkaç cümle içersin. Gerçek bir astrologun yazdığı gibi "
        f"doğal görünsün, başında/sonunda 'işte yorumunuz' gibi meta açıklama "
        f"olmasın, direkt yorumla başla."
    )
    try:
        adapter = get_adapter("groq")
        return adapter.generate([], prompt)
    except ProviderError as e:
        raise AstrologyError(f"Burç yorumu üretilemedi: {e}") from e
    except Exception as e:
        raise AstrologyError(f"Burç yorumu üretilemedi: {e}") from e


def _parse_birth_input(text: str):
    """'15.03.1990 14:30 İstanbul' formatını ayrıştırır."""
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3:
        raise AstrologyError(
            "Format: GG.AA.YYYY SS:DD Şehir\nÖrnek: 15.03.1990 14:30 İstanbul"
        )
    date_part, time_part, city = parts[0], parts[1], parts[2]
    try:
        day, month, year = [int(x) for x in date_part.split(".")]
        hour, minute = [int(x) for x in time_part.split(":")]
    except ValueError:
        raise AstrologyError(
            "Tarih/saat anlaşılamadı. Format: GG.AA.YYYY SS:DD Şehir\n"
            "Örnek: 15.03.1990 14:30 İstanbul"
        )
    return year, month, day, hour, minute, city


def get_birth_chart(text: str) -> str:
    if not config.FREEASTROLOGY_API_KEY:
        raise AstrologyError("FREEASTROLOGY_API_KEY tanımlı değil.")
    year, month, day, hour, minute, city = _parse_birth_input(text)
    headers = {"x-api-key": config.FREEASTROLOGY_API_KEY, "Content-Type": "application/json"}

    try:
        geo_data = _post_with_retry(
            "https://json.freeastrologyapi.com/geo-details",
            headers, {"location": city}, 20, "Konum servisi",
        )
        if not geo_data:
            raise AstrologyError(f"'{city}' konumu bulunamadı.")
        loc = geo_data[0]
        latitude, longitude, timezone = loc["latitude"], loc["longitude"], loc["timezone_offset"]
    except AstrologyError:
        raise
    except Exception as e:
        raise AstrologyError(f"Konum bilgisi alınamadı: {e}") from e

    try:
        planets_data = _post_with_retry(
            "https://json.freeastrologyapi.com/western/planets",
            headers,
            {
                "year": year, "month": month, "date": day,
                "hours": hour, "minutes": minute, "seconds": 0,
                "latitude": latitude, "longitude": longitude, "timezone": timezone,
                "config": {"observation_point": "topocentric", "ayanamsha": "tropical", "language": "tr"},
            },
            30, "Doğum haritası servisi",
        )
        output = planets_data.get("output", [])
        if not output:
            raise AstrologyError("Doğum haritası hesaplanamadı.")
    except AstrologyError:
        raise
    except Exception as e:
        raise AstrologyError(f"Doğum haritası hesaplanamadı: {e}") from e

    lines = [f"🌌 Doğum Haritası — {city}, {day:02d}.{month:02d}.{year} {hour:02d}:{minute:02d}\n"]
    for p in output:
        name = p["planet"].get("tr") or p["planet"].get("en")
        sign_name = p["zodiac_sign"]["name"].get("tr") or p["zodiac_sign"]["name"].get("en")
        degree = p["normDegree"]
        retro = " (Retro)" if str(p.get("isRetro", "")).lower() == "true" else ""
        lines.append(f"• {name}: {sign_name} {degree:.1f}°{retro}")
    raw_chart = "\n".join(lines)

    # Ham verileri Gemini'ye yorumlatıyoruz (gerçek hesaplanmış konumlara dayanan bir yorum)
    try:
        interpretation_prompt = (
            "Aşağıda bir kişinin gerçek, hesaplanmış doğum haritası (gezegen "
            "konumları) var. Bu verilere dayanarak, Türkçe, sıcak ve anlaşılır "
            "bir astrolojik yorum yaz: genel kişilik eğilimleri, güçlü yönleri, "
            "dikkat etmesi gerekebilecek noktalar. 4-6 paragraf, abartılı "
            "kehanetlerden kaçın, dengeli bir üslup kullan.\n\n" + raw_chart
        )
        adapter = get_adapter("groq")
        interpretation = adapter.generate([], interpretation_prompt)
    except (ProviderError, Exception) as e:
        logger.warning(f"Doğum haritası yorumu üretilemedi: {e}")
        interpretation = None

    if interpretation:
        return f"{raw_chart}\n\n— — —\n\n🔮 Yorum:\n{interpretation}"
    return raw_chart + "\n\n(Not: AI yorumu şu an üretilemedi, sadece ham veriler gösteriliyor.)"
