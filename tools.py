"""
Bilgi & Araçlar: hava durumu, döviz kuru, WolframAlpha, web arama,
hava kalitesi, link güvenlik taraması, NASA günün fotoğrafı.
"""
import base64
import logging

import requests

import config

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Bir araç isteği başarısız olduğunda fırlatılır."""


def get_weather(city: str) -> str:
    if not config.OPENWEATHER_API_KEY:
        raise ToolError("OPENWEATHER_API_KEY tanımlı değil.")
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": config.OPENWEATHER_API_KEY, "units": "metric", "lang": "tr"},
            timeout=20,
        )
        if resp.status_code == 404:
            raise ToolError(f"'{city}' adında bir şehir bulunamadı.")
        resp.raise_for_status()
        data = resp.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        name = data.get("name", city)
        return (
            f"📍 {name}\n🌡️ {temp}°C (hissedilen {feels}°C)\n"
            f"☁️ {desc}\n💧 Nem: %{humidity}\n💨 Rüzgar: {wind} m/s"
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Hava durumu alınamadı: {e}") from e


def get_exchange_rate(query: str) -> str:
    if not config.EXCHANGERATE_API_KEY:
        raise ToolError("EXCHANGERATE_API_KEY tanımlı değil.")
    parts = query.upper().split()
    amount = 1.0
    if len(parts) == 3:
        try:
            amount = float(parts[0].replace(",", "."))
        except ValueError:
            raise ToolError("Miktarı anlayamadım. Örn: '100 USD TRY'")
        base, target = parts[1], parts[2]
    elif len(parts) == 2:
        base, target = parts[0], parts[1]
    else:
        raise ToolError("Format: 'USD TRY' ya da '100 USD TRY' şeklinde yaz.")
    try:
        resp = requests.get(
            f"https://v6.exchangerate-api.com/v6/{config.EXCHANGERATE_API_KEY}/pair/{base}/{target}/{amount}",
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            raise ToolError(data.get("error-type", "Kur bilgisi alınamadı."))
        rate = data["conversion_rate"]
        result = data.get("conversion_result", rate)
        return f"💱 {amount:g} {base} = {result:.2f} {target}\n(1 {base} = {rate:.4f} {target})"
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Döviz kuru alınamadı: {e}") from e


def ask_wolfram(query: str) -> str:
    if not config.WOLFRAMALPHA_API_KEY:
        raise ToolError("WOLFRAMALPHA_API_KEY tanımlı değil.")
    try:
        resp = requests.get(
            "https://api.wolframalpha.com/v1/result",
            params={"appid": config.WOLFRAMALPHA_API_KEY, "i": query},
            timeout=20,
        )
        if resp.status_code == 501:
            raise ToolError("Bu soruya kısa bir cevap üretemedim. Farklı bir şekilde sormayı dene.")
        resp.raise_for_status()
        return f"🧮 {resp.text}"
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"WolframAlpha sorgusu başarısız: {e}") from e


def web_search_tavily(query: str) -> str:
    if not config.TAVILY_API_KEY:
        raise ToolError("TAVILY_API_KEY tanımlı değil.")
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": config.TAVILY_API_KEY, "query": query, "max_results": 5, "include_answer": True},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = []
        if data.get("answer"):
            lines.append(f"📝 {data['answer']}")
        for r in data.get("results", [])[:5]:
            lines.append(f"🔗 {r['title']}\n{r['url']}")
        if not lines:
            raise ToolError("Sonuç bulunamadı.")
        return "\n\n".join(lines)
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Web araması başarısız: {e}") from e


def get_air_quality(city: str) -> str:
    if not config.AQICN_API_KEY:
        raise ToolError("AQICN_API_KEY tanımlı değil.")
    try:
        resp = requests.get(
            f"https://api.waqi.info/feed/{city}/", params={"token": config.AQICN_API_KEY}, timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            raise ToolError(f"'{city}' için hava kalitesi verisi bulunamadı.")
        d = data["data"]
        aqi = d["aqi"]
        if isinstance(aqi, str):
            raise ToolError(f"'{city}' için sayısal AQI verisi yok.")
        level = (
            "İyi 🟢" if aqi <= 50 else
            "Orta 🟡" if aqi <= 100 else
            "Hassas gruplar için sağlıksız 🟠" if aqi <= 150 else
            "Sağlıksız 🔴" if aqi <= 200 else
            "Çok sağlıksız 🟣" if aqi <= 300 else
            "Tehlikeli ⚫"
        )
        city_name = d.get("city", {}).get("name", city)
        return f"🌬️ {city_name}\nAQI: {aqi} — {level}"
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Hava kalitesi alınamadı: {e}") from e


def scan_url_virustotal(url: str) -> str:
    if not config.VIRUSTOTAL_API_KEY:
        raise ToolError("VIRUSTOTAL_API_KEY tanımlı değil.")
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
            timeout=30,
        )
        if resp.status_code == 404:
            submit = requests.post(
                "https://www.virustotal.com/api/v3/urls",
                headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
                data={"url": url},
                timeout=30,
            )
            submit.raise_for_status()
            return "🛡️ Bu link ilk kez taranıyor. Sonucu görmek için birkaç saniye sonra aynı linki tekrar gönder."
        resp.raise_for_status()
        data = resp.json()
        stats = data["data"]["attributes"]["last_analysis_stats"]
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        if malicious == 0 and suspicious == 0:
            verdict = "✅ Güvenli görünüyor"
        else:
            verdict = f"⚠️ Riskli! {malicious} motor zararlı, {suspicious} motor şüpheli işaretledi"
        return f"🛡️ {url}\n{verdict}\n(Zararsız: {harmless}, Zararlı: {malicious}, Şüpheli: {suspicious})"
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Link taranamadı: {e}") from e


def get_nasa_apod():
    """(başlık+açıklama, görsel_url) tuple döner."""
    api_key = config.NASA_API_KEY or "DEMO_KEY"
    try:
        resp = requests.get("https://api.nasa.gov/planetary/apod", params={"api_key": api_key}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        title = data.get("title", "NASA Günün Fotoğrafı")
        explanation = data.get("explanation", "")
        image_url = data.get("url", "")
        caption = f"🚀 {title}\n\n{explanation[:800]}"
        return caption, image_url
    except Exception as e:
        raise ToolError(f"NASA verisi alınamadı: {e}") from e
