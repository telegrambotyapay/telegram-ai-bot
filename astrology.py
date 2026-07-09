"""
Astroloji özellikleri:
- get_horoscope(): günlük/haftalık/aylık burç yorumu (astrology-api.io)
- get_birth_chart(): doğum haritası (freeastrologyapi.com)
"""
import logging

import requests

import config

logger = logging.getLogger(__name__)


class AstrologyError(Exception):
    """Astroloji isteği başarısız olduğunda fırlatılır."""


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
    """period: 'daily', 'weekly' ya da 'monthly'"""
    if not config.ASTROLOGY_API_IO_KEY:
        raise AstrologyError("ASTROLOGY_API_IO_KEY tanımlı değil.")
    sign = _normalize_sign(sign_text)
    try:
        resp = requests.post(
            f"https://api.astrology-api.io/api/v3/horoscope/{period}",
            headers={
                "Authorization": f"Bearer {config.ASTROLOGY_API_IO_KEY}",
                "Content-Type": "application/json",
            },
            json={"sign": sign, "language": "en"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get("horoscope") or data.get("content") or data.get("prediction")
            or data.get("text") or data.get("reading")
        )
        if isinstance(text, dict):
            text = text.get("general") or text.get("text") or str(text)
        if not text:
            raise AstrologyError(f"Beklenmeyen cevap formatı, servis değişmiş olabilir.")
        return str(text)
    except AstrologyError:
        raise
    except requests.HTTPError as e:
        raise AstrologyError(f"Burç yorumu alınamadı ({e}). Servis endpoint'i değişmiş olabilir.") from e
    except Exception as e:
        raise AstrologyError(f"Burç yorumu alınamadı: {e}") from e


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
        geo_resp = requests.post(
            "https://json.freeastrologyapi.com/geo-details",
            headers=headers, json={"location": city}, timeout=20,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise AstrologyError(f"'{city}' konumu bulunamadı.")
        loc = geo_data[0]
        latitude, longitude, timezone = loc["latitude"], loc["longitude"], loc["timezone_offset"]
    except AstrologyError:
        raise
    except Exception as e:
        raise AstrologyError(f"Konum bilgisi alınamadı: {e}") from e

    try:
        planets_resp = requests.post(
            "https://json.freeastrologyapi.com/western/planets",
            headers=headers,
            json={
                "year": year, "month": month, "date": day,
                "hours": hour, "minutes": minute, "seconds": 0,
                "latitude": latitude, "longitude": longitude, "timezone": timezone,
                "config": {"observation_point": "topocentric", "ayanamsha": "tropical", "language": "tr"},
            },
            timeout=30,
        )
        planets_resp.raise_for_status()
        planets_data = planets_resp.json()
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
    return "\n".join(lines)
