import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from collections import defaultdict

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    MAX_FAILED_ATTEMPTS,
    BLOCK_DURATION_MINUTES,
    RATE_LIMIT_PER_MINUTE,
    ADMIN_RATE_LIMIT_PER_MINUTE,
    get_api_key
)
from app.database import SessionLocal
from app.models import BlockedIP, SecurityLog

logger = logging.getLogger("uvicorn.error")

# ==========================================
# 1. Regex Patterns for Attacks
# ==========================================

# Known vulnerability scanners & tools
SCANNER_UA_REGEX = re.compile(
    r"(nmap|nikto|sqlmap|masscan|w3af|acunetix|dirbuster|gobuster|havij|netsparker|openvas|nessus|zgrab|arachni)",
    re.IGNORECASE
)

# Common scan / exploit probing paths
MALICIOUS_PATHS_REGEX = re.compile(
    r"(\.env|wp-admin|wp-login|\.git|phpmyadmin|eval-stdin|etc/passwd|win\.ini|boaform|cgi-bin|solr|actuator)",
    re.IGNORECASE
)

# SQL Injection signature patterns
SQLI_REGEX = re.compile(
    r"(\b(union(\s+all)?\s+select|select\s+.*\s+from|insert\s+into|drop\s+table|alter\s+table|delete\s+from|update\s+.*\s+set)\b|"
    r"(\b(or|and)\s+['\"0-9]+(\s*)=(\s*)['\"0-9]+)|"
    r"(\b(sleep|benchmark)\s*\(\s*\d+\s*\))|"
    r"(\bexec(\s*|\s+xp_cmdshell)\s*\(?)|"
    r"(--|/\*|\*/|;\s*(drop|delete|insert|update|alter)))",
    re.IGNORECASE
)

# ==========================================
# 2. In-Memory Tracking for Speed & Anti-DDoS
# ==========================================

# Rate limiter: ip -> list of timestamps
_rate_limits: Dict[str, list] = defaultdict(list)

# Failed API key attempts: ip -> count
_failed_attempts: Dict[str, int] = defaultdict(int)

# In-memory blocked IPs cache: ip -> unblock_timestamp (float)
_blocked_ips_cache: Dict[str, float] = {}

def get_client_ip(request: Request) -> str:
    """Extract real client IP considering reverse proxies (Cloudflare, Nginx, etc.)"""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

def is_ip_blocked(ip: str) -> Tuple[bool, str]:
    """Check if an IP is currently blocked (via cache or database)"""
    now = time.time()
    
    # Check cache first for high performance
    if ip in _blocked_ips_cache:
        expire_at = _blocked_ips_cache[ip]
        if expire_at > now:
            return True, "IP is blocked in active session cache"
        else:
            del _blocked_ips_cache[ip]

    # Check database
    db = SessionLocal()
    try:
        blocked = db.query(BlockedIP).filter(BlockedIP.ip_address == ip).first()
        if blocked:
            if blocked.is_permanent:
                _blocked_ips_cache[ip] = now + 86400 * 365
                return True, blocked.reason
            if blocked.blocked_until and blocked.blocked_until > datetime.utcnow():
                remaining_seconds = (blocked.blocked_until - datetime.utcnow()).total_seconds()
                _blocked_ips_cache[ip] = now + remaining_seconds
                return True, blocked.reason
            else:
                # Expired block
                db.delete(blocked)
                db.commit()
    except Exception as e:
        logger.error(f"Error checking blocked IP in DB: {e}")
    finally:
        db.close()

    return False, ""

def block_ip(ip: str, reason: str, duration_minutes: int = BLOCK_DURATION_MINUTES, permanent: bool = False):
    """Block an IP address in memory and in the database"""
    now = time.time()
    expire_timestamp = now + (duration_minutes * 60) if not permanent else now + (86400 * 365 * 10)
    _blocked_ips_cache[ip] = expire_timestamp

    db = SessionLocal()
    try:
        blocked = db.query(BlockedIP).filter(BlockedIP.ip_address == ip).first()
        blocked_until = datetime.utcnow() + timedelta(minutes=duration_minutes) if not permanent else None
        
        if blocked:
            blocked.reason = reason
            blocked.failed_attempts += 1
            blocked.blocked_until = blocked_until
            blocked.is_permanent = permanent
        else:
            blocked = BlockedIP(
                ip_address=ip,
                reason=reason,
                failed_attempts=1,
                blocked_until=blocked_until,
                is_permanent=permanent
            )
            db.add(blocked)
        
        # Log to security log
        log = SecurityLog(
            ip_address=ip,
            event_type="IP_BLOCKED",
            details=f"Blocked for {duration_minutes}m: {reason}"
        )
        db.add(log)
        db.commit()
        logger.warning(f"🚫 BLOCKED IP [{ip}]: {reason}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving blocked IP to DB: {e}")
    finally:
        db.close()

def unblock_ip(ip: str) -> bool:
    """Unblock an IP address"""
    if ip in _blocked_ips_cache:
        del _blocked_ips_cache[ip]
    if ip in _failed_attempts:
        del _failed_attempts[ip]

    db = SessionLocal()
    try:
        blocked = db.query(BlockedIP).filter(BlockedIP.ip_address == ip).first()
        if blocked:
            db.delete(blocked)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error unblocking IP: {e}")
        return False
    finally:
        db.close()

def record_failed_api_attempt(ip: str, endpoint: str):
    """Track failed API key access. If exceeds threshold, immediately block the IP!"""
    _failed_attempts[ip] += 1
    attempts = _failed_attempts[ip]

    # Log security event
    db = SessionLocal()
    try:
        log = SecurityLog(
            ip_address=ip,
            event_type="INVALID_API_KEY",
            details=f"Failed API Key attempt #{attempts} of {MAX_FAILED_ATTEMPTS}",
            endpoint=endpoint
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()

    if attempts >= MAX_FAILED_ATTEMPTS:
        block_ip(
            ip=ip,
            reason=f"Exceeded {MAX_FAILED_ATTEMPTS} failed/invalid API Key attempts",
            duration_minutes=BLOCK_DURATION_MINUTES
        )

def check_rate_limit(ip: str, limit_per_minute: int = RATE_LIMIT_PER_MINUTE) -> bool:
    """Sliding window rate limiter. Returns False if limit is exceeded."""
    now = time.time()
    window = now - 60.0
    
    # Filter out requests older than 1 minute
    timestamps = [t for t in _rate_limits[ip] if t > window]
    timestamps.append(now)
    _rate_limits[ip] = timestamps

    # If bursting at more than 2x rate limit, immediately block IP for DDoS protection
    if len(timestamps) > limit_per_minute * 2:
        block_ip(ip, "DDoS / Extreme request flood detected", duration_minutes=30)
        return False

    return len(timestamps) <= limit_per_minute

# ==========================================
# 3. High Security ASGI Middleware
# ==========================================

class HighSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = get_client_ip(request)
        path = request.url.path
        query_str = str(request.url.query)
        user_agent = request.headers.get("user-agent", "")

        # 1. Check if IP is currently blocked
        blocked, reason = is_ip_blocked(ip)
        if blocked:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "status": False,
                    "error": "Access Denied: Your IP has been blocked by the security firewall.",
                    "ip": ip,
                    "reason": reason
                }
            )

        # 2. Scanner / Nmap / Tools Detection
        if SCANNER_UA_REGEX.search(user_agent):
            block_ip(ip, f"Security Scanner detected in User-Agent: {user_agent[:50]}", duration_minutes=120)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"status": False, "error": "Malicious scanner probe detected and blocked."}
            )

        # 3. Malicious Path / Probing Detection (e.g. /.env, /wp-admin, /phpmyadmin)
        if MALICIOUS_PATHS_REGEX.search(path):
            block_ip(ip, f"Probing suspicious/restricted path: {path[:50]}", duration_minutes=60)
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": False, "error": "Not Found"}
            )

        # 4. SQL Injection vector detection in URL and Query String
        if SQLI_REGEX.search(path) or SQLI_REGEX.search(query_str):
            block_ip(ip, "SQL Injection payload detected in request URL/query parameters", duration_minutes=180)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"status": False, "error": "SQL Injection attempt detected and blocked."}
            )

        # 5. Anti-DDoS Rate Limiting
        # Sensitive routes get stricter rate limit
        rate_limit = ADMIN_RATE_LIMIT_PER_MINUTE if "/login" in path else RATE_LIMIT_PER_MINUTE
        if not check_rate_limit(ip, rate_limit):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "status": False,
                    "error": "Too Many Requests: Rate limit exceeded. Please slow down."
                },
                headers={"Retry-After": "60"}
            )

        # Process the request
        response = await call_next(request)

        # Add High Security Hardening Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
