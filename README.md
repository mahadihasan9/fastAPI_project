# ⚡ Photo API Hub & Auto-Compression Engine

A high-performance, secure, and modern **FastAPI** service featuring automated image compression (1KB–100KB target), responsive photo gallery, anti-DDoS security firewall, and authenticated random image distribution APIs.

Optimized for **Google Chrome, Mozilla Firefox, and Android Mobile WebKit** browsers.

---

## 🌟 Key Features

1. **🔐 Admin Portal Authentication**:
   - Clean, modern administrator login portal.
   - Protected by a secret password loaded dynamically from `adminkey.txt` (Default: `admin`).
   - Hardened against credential probing and brute-force attempts.

2. **📸 Smart Image Auto-Compression (1KB – 100KB)**:
   - Interactive size slider and numeric display to choose any target size from **1 KB up to 100 KB** (default: 50 KB).
   - Accepts large images (1MB+ or multi-megapixel) and compresses them to the exact target size in `.jpg` format using Pillow.
   - The encoder never overshoots the target: it binary-searches the highest JPEG quality that fits, then progressively downscales resolution for tiny targets (1–5 KB).
   - Auto-orients images and handles transparency (RGBA/PNG) with clean background blending.
   - Saves compressed outputs with unique hexadecimal/UUID identifiers.

3. **🖼️ Responsive Photo Gallery & Lightbox Viewer**:
   - Modern photo cards with smooth hover effects, size badges, resolution indicators, and timestamps.
   - Interactive fullscreen **Lightbox Modal** for high-resolution image preview with download and link copy buttons.
   - Toggle switcher between **🖼️ Gallery Grid** and **📋 List Table** views (remembers user preference via `localStorage`).

4. **📋 One-Click API Integration**:
   - **Download Photo API**: `GET /api/v1/photo/random?api_key=...` — Streams a random `.jpg` image directly.
   - **JSON Base64 API**: `GET /api/v1/photo/random/json?api_key=...` — Returns structured JSON containing base64 payload and string length.
   - Dedicated buttons to copy formatted API endpoints to clipboard with instant toast notifications.

5. **🛡️ High-Security Firewall Suite**:
   - **API Key Abuse & IP Auto-Blocking**: 5 failed or missing API key attempts immediately blacklist the client IP address.
   - **Anti-DDoS & Rate Limiting**: Token-bucket sliding window rate limiter protects endpoints against volumetric floods.
   - **Nmap & Scanner Detection**: Identifies and terminates requests matching known scanning tools (Nmap, Nikto, SQLmap, Acunetix, etc.).
   - **SQL Injection Prevention**: Active URL & Query vector analysis blocks malicious payloads before reaching database handlers.
   - **Admin Unblock Panel**: Blocked IPs and audit trails can be reviewed and unblocked directly from the dashboard.

6. **🗄️ MySQL Database with SQLite Graceful Fallback**:
   - Native MySQL support via SQLAlchemy ORM.
   - Automatically falls back to SQLite (`app.db`) if MySQL is temporarily unreachable locally, ensuring zero downtime during development.

7. **🐳 Docker & Containerization Ready**:
   - Production-ready `Dockerfile` and `docker-compose.yml` for multi-container deployment (FastAPI + MySQL 8.0).

---

## 📁 Project Structure

```
fastAPI_project/
├── adminkey.txt            # Administrator login password
├── apikey.txt              # Secret key for public API requests
├── requirements.txt        # Python package dependencies
├── Dockerfile              # Docker container build specification
├── docker-compose.yml      # Multi-container service (FastAPI + MySQL)
├── .env                    # Environment variables & database URI
├── .gitignore              # Git ignore rules (prevents tracking caches & db)
├── COMMANDS.md             # Complete CLI command reference cheatsheet
├── README.md               # English project documentation
├── app/
│   ├── config.py           # Configuration & dynamic key loading
│   ├── database.py         # SQLAlchemy engine with SQLite fallback
│   ├── models.py           # Photo, BlockedIP, SecurityLog schemas
│   ├── image_utils.py      # Pillow smart compression algorithms
│   ├── security.py         # Anti-DDoS, SQLi & scanner firewall middleware
│   ├── static/             # Static frontend assets
│   │   ├── css/style.css   # Glassmorphic responsive styling
│   │   └── js/app.js       # Dynamic upload, gallery, copy & modal scripts
│   └── templates/          # Jinja2 HTML templates
│       ├── login.html      # Administrator login interface
│       └── dashboard.html  # Full administrative control dashboard
├── uploads/                # Directory storing compressed .jpg photos
└── main.py                 # Application entry point & API route definitions
```

---

## 🔑 Default Credentials & Keys

| Key Item | File Location | Default Value | Notes |
|---|---|---|---|
| **Admin Password** | `adminkey.txt` | `admin` | Used to authenticate at `/` and access `/dashboard`. `ADMIN_PASSWORD` env var overrides it |
| **Public API Key** | `apikey.txt` | `admin` | Required in query string (`?api_key=...`) or header (`X-API-Key`). `API_KEY` env var overrides it |

> You can update `adminkey.txt` and `apikey.txt` anytime with your custom keys. The server loads changes automatically without restart.
>
> **For Docker/VPS deployments** prefer the environment variables (`-e ADMIN_PASSWORD=... -e API_KEY=...`) —
> both key files are excluded from the image via `.dockerignore` so secrets are never published.
> See [COMMANDS.md](file:///home/drunken_poet/Documents/fastAPI_project/COMMANDS.md) section 6 for the full VPS guide.

---

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
Start the server using either of the following commands:

```bash
# Option A: Direct Python runner
python main.py

# Option B: Standard Uvicorn reload
uvicorn main:app --reload --port 8000
```

### 3. Open in Browser
- **Admin Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📡 Public API Specifications

### 1. Random Photo Direct Download API
```http
GET /api/v1/photo/random?api_key=my_secure_api_key_2026
```
- **Response**: Directly streams a random compressed `.jpg` file (`Content-Type: image/jpeg`).

### 2. Random Photo JSON API
```http
GET /api/v1/photo/random/json?api_key=my_secure_api_key_2026
```
- **Response**:
```json
{
  "status": true,
  "fileFormat": "jpg",
  "encode": "base64",
  "size": 142850,
  "data": "/9j/4AAQSkZJRgABAQ..."
}
```

### 3. Specific Photo Download API
```http
GET /api/v1/photo/<photo_id>?api_key=admin
```
- **Response**: Streams the image matching the unique `<photo_id>`.

---

## 🐳 Docker Deployment

For complete CLI commands, see [COMMANDS.md](file:///home/drunken_poet/Documents/fastAPI_project/COMMANDS.md).

### Build Docker Image
```bash
docker build -t fastapi-photo-engine:latest .
```

### Run Container
```bash
docker run -d -p 8000:8000 --name photo_engine fastapi-photo-engine:latest
```

### Run with Docker Compose (FastAPI + MySQL 8.0)
```bash
docker-compose up --build -d
```

---

## 📱 Cross-Browser Compatibility & Mobile Layout
- **Google Chrome**: Full desktop and mobile support.
- **Mozilla Firefox**: Full desktop and Gecko mobile support with custom `-moz-` range styling.
- **Android WebKit**: Touch-friendly gallery controls, custom slider track/thumb, and mobile-safe clipboard actions.
- **Phone / small-screen layout**: single-column workspace, wrapped API URLs, horizontally scrollable tables (optional columns hidden), full-width copy buttons and toasts. All grid tracks use `minmax(0, 1fr)` + `min-width: 0` so long unbreakable strings (API URLs, file names) can never stretch the page past the viewport.
