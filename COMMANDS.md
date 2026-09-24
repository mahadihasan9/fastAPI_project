# 🛠️ CLI Cheatsheet & Command Reference

This document provides a complete reference for running, developing, testing, and managing the FastAPI Photo API application with Python, Docker, and Docker Compose.

---

## 🐍 1. Python Local Development

### Activate Virtual Environment
```bash
# If using existing environment:
source /home/drunken_poet/env/bin/activate

# Or create and activate a new virtual environment:
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Server (Development Mode)
You can start the server using either of the following commands:

```bash
# Method 1: Direct Python execution (built-in uvicorn launcher)
python main.py

# Method 2: Standard FastAPI reload command
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Run Server (Production Mode)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🐳 2. Docker Commands

### Build Docker Image
```bash
# Build with tag 'fastapi-photo-engine:latest'
docker build -t fastapi-photo-engine:latest .

# Build without using cache (clean build)
docker build --no-cache -t fastapi-photo-engine:latest .
```

### Run Docker Container
```bash
# Run in background (detached mode) on port 8000
docker run -d -p 8000:8000 --name photo_engine fastapi-photo-engine:latest

# Run with persistent storage for uploaded photos and configuration keys:
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/adminkey.txt:/app/adminkey.txt \
  -v $(pwd)/apikey.txt:/app/apikey.txt \
  --name photo_engine \
  fastapi-photo-engine:latest
```

### Monitor & Inspect Containers
```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# View container logs (follow in real time)
docker logs -f photo_engine

# Check resource usage (CPU, Memory)
docker stats photo_engine

# Open an interactive shell inside the container
docker exec -it photo_engine /bin/bash
```

### Stop, Start & Restart Container
```bash
# Stop the running container
docker stop photo_engine

# Start the container again
docker start photo_engine

# Restart the container
docker restart photo_engine
```

### Remove Container
```bash
# Remove a stopped container
docker rm photo_engine

# Force stop and remove container in one command
docker rm -f photo_engine
```

### Manage Docker Images
```bash
# List available images
docker images

# Remove the built image
docker rmi fastapi-photo-engine:latest

# Force remove the image (if tagged in multiple places)
docker rmi -f fastapi-photo-engine:latest

# Remove unused/dangling build cache and images
docker system prune -f
```

---

## 🐙 3. Docker Compose Commands (FastAPI + MySQL 8.0)

### Start Services
```bash
# Build images and start all containers in background
docker-compose up --build -d

# Start without rebuilding
docker-compose up -d
```

### Check Status & Logs
```bash
# List compose services
docker-compose ps

# Stream logs of all services
docker-compose logs -f

# View logs for web app only
docker-compose logs -f web

# View logs for MySQL only
docker-compose logs -f mysql_db
```

### Stop & Clean Up
```bash
# Stop services without deleting containers
docker-compose stop

# Start stopped services
docker-compose start

# Stop and remove containers and networks
docker-compose down

# Stop and remove containers, networks, and persistent database volumes
docker-compose down -v
```

---

## 🌐 4. API Testing Commands (cURL)

### Test Web Portal & Health
```bash
curl -I http://127.0.0.1:8000/
```

### Test Random Photo Download API (Saves image directly)
```bash
curl -o random_photo.jpg "http://127.0.0.1:8000/api/v1/photo/random?api_key=my_secure_api_key_2026"
```

### Test JSON Base64 API
```bash
curl -s "http://127.0.0.1:8000/api/v1/photo/random/json?api_key=my_secure_api_key_2026" | jq .
```

### Test Download Specific Photo by ID
```bash
curl -o photo.jpg "http://127.0.0.1:8000/api/v1/photo/<PHOTO_ID>?api_key=my_secure_api_key_2026"
```

### Test Security Firewall (Unauthorized Request)
```bash
# Calling without API key returns 403 Forbidden
curl -i "http://127.0.0.1:8000/api/v1/photo/random"
```
*(Sending 5 unauthorized requests will automatically block the caller's IP).*

---

## 🔑 5. Configuration Files Reference

| File | Purpose | Notes |
|---|---|---|
| `adminkey.txt` | Administrator Login Password | Read dynamically on every login attempt. Overridden by the `ADMIN_PASSWORD` env var |
| `apikey.txt` | Public API Secret Key | Required as `?api_key=...` or `X-API-Key` header. Overridden by the `API_KEY` env var |
| `.env` | Environment Variables | Controls database URL, rate limits, and fallback |
| `.gitignore` | Git Ignore Rules | Prevents uploading secrets, databases, and caches |
| `Dockerfile` | Container Definition | Python 3.11-slim container specification |
| `docker-compose.yml` | Multi-container Orchestration | Runs FastAPI and MySQL 8.0 together |

---

## 🖥️ 6. VPS Deployment (pull the published image)

Published public image (linux/amd64): `drunken0poet/fastapi-photo-engine:latest`

### Pull and run (secrets as environment variables — recommended)
```bash
docker pull drunken0poet/fastapi-photo-engine:latest     # or pin: :1.1.0

docker run -d \
  --name photo_engine \
  --restart unless-stopped \
  -p 80:8000 \
  -e ADMIN_PASSWORD='YourStrongAdminPassword' \
  -e API_KEY='YourStrongApiKey' \
  -e SESSION_SECRET_KEY='a_long_random_session_secret_string' \
  -e FALLBACK_TO_SQLITE=True \
  -e RATE_LIMIT_PER_MINUTE=60 \
  -e ADMIN_RATE_LIMIT_PER_MINUTE=10 \
  -v photo_uploads:/app/uploads \
  drunken0poet/fastapi-photo-engine:latest
```
> If port 80 is taken (or you don't want root), use `-p 8080:8000` and put Nginx/Caddy in front.

### Alternative: mount your own key files instead of env vars
```bash
mkdir -p /opt/photo_engine/uploads && cd /opt/photo_engine
printf 'YourStrongAdminPassword' > adminkey.txt
printf 'YourStrongApiKey'        > apikey.txt

docker run -d --name photo_engine --restart unless-stopped -p 8080:8000 \
  -v /opt/photo_engine/uploads:/app/uploads \
  -v /opt/photo_engine/adminkey.txt:/app/adminkey.txt \
  -v /opt/photo_engine/apikey.txt:/app/apikey.txt \
  drunken0poet/fastapi-photo-engine:latest
```
> ⚠️ The image contains **no** keys (they are excluded via `.dockerignore`). If you start the container
> without env vars and without mounted files, it auto-creates the defaults
> `admin@secret123` / `my_secure_api_key_2026` — change them immediately.

### Compose file for the VPS
```yaml
services:
  photo_engine:
    image: drunken0poet/fastapi-photo-engine:latest
    container_name: photo_engine
    restart: unless-stopped
    ports:
      - "8080:8000"
    environment:
      - ADMIN_PASSWORD=YourStrongAdminPassword
      - API_KEY=YourStrongApiKey
      - SESSION_SECRET_KEY=a_long_random_session_secret_string
      - FALLBACK_TO_SQLITE=True
    volumes:
      - ./uploads:/app/uploads
```
```bash
docker compose up -d && docker compose logs -f
```

### Update to a newer release
```bash
docker pull drunken0poet/fastapi-photo-engine:latest
docker rm -f photo_engine
docker run -d ... (same command as above)
# or with compose:
docker compose pull && docker compose up -d
```

### Verify + firewall
```bash
curl -I http://<VPS_IP>:8080/                       # 200 -> login page
curl -I http://<VPS_IP>:8080/docs                   # 200 -> swagger
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp     # open only what you need
```
> The app already sends `X-Forwarded-For` aware logging; place it behind Nginx/Caddy for HTTPS.
