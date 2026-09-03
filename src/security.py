import os
import re
import time
import asyncio
from collections import defaultdict, deque
from threading import Lock
from typing import Tuple, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ==============================================================================
# 1. Rate Limiting & Resource Quotas
# ==============================================================================
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "3600"))
MAX_CONCURRENT_RESEARCH = int(os.getenv("MAX_CONCURRENT_RESEARCH", "2"))
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "500"))

class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter with dual engine:
    1. Redis engine if reachable (for distributed/VPS multi-process scaling).
    2. Resilient in-memory thread-safe fallback if Redis is unavailable.
    """
    def __init__(self):
        self.redis_client = None
        self._init_redis()
        # In-memory fallback
        self._memory_store = defaultdict(deque)
        self._lock = Lock()

    def _init_redis(self):
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        if redis_host:
            try:
                import redis
                client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                    decode_responses=True
                )
                client.ping()
                self.redis_client = client
            except Exception:
                self.redis_client = None

    def check(self, client_ip: str) -> Tuple[bool, int]:
        """
        Checks if client_ip has exceeded rate limit.
        Returns (is_allowed: bool, retry_after_seconds: int).
        """
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        # Try Redis first
        if self.redis_client:
            try:
                key = f"ratelimit:ip:{client_ip}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS)
                _, _, count, _ = pipe.execute()
                
                if count > RATE_LIMIT_MAX_REQUESTS:
                    return False, RATE_LIMIT_WINDOW_SECONDS
                return True, 0
            except Exception:
                # If Redis temporarily fails, fall back to in-memory seamlessly
                pass

        # In-memory fallback
        with self._lock:
            timestamps = self._memory_store[client_ip]
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()
                
            if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
                oldest = timestamps[0]
                retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest))
                return False, max(1, retry_after)
                
            timestamps.append(now)
            return True, 0

    def get_status(self, client_ip: str) -> dict:
        """
        Returns current rate limit quota usage for client_ip without incrementing.
        """
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        # Try Redis first
        if self.redis_client:
            try:
                key = f"ratelimit:ip:{client_ip}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zrange(key, 0, 0, withscores=True)
                _, count, oldest_items = pipe.execute()
                
                remaining = max(0, RATE_LIMIT_MAX_REQUESTS - count)
                reset_in = 0
                if count >= RATE_LIMIT_MAX_REQUESTS and oldest_items:
                    reset_in = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest_items[0][1])))
                return {
                    "limit": RATE_LIMIT_MAX_REQUESTS,
                    "used": count,
                    "remaining": remaining,
                    "reset_in_seconds": reset_in,
                    "window_hours": round(RATE_LIMIT_WINDOW_SECONDS / 3600, 1),
                    "algorithm": "Sliding Window Log"
                }
            except Exception:
                pass

        # In-memory fallback
        with self._lock:
            timestamps = self._memory_store[client_ip]
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()
            count = len(timestamps)
            remaining = max(0, RATE_LIMIT_MAX_REQUESTS - count)
            reset_in = 0
            if count >= RATE_LIMIT_MAX_REQUESTS and timestamps:
                reset_in = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - timestamps[0])))
            return {
                "limit": RATE_LIMIT_MAX_REQUESTS,
                "used": count,
                "remaining": remaining,
                "reset_in_seconds": reset_in,
                "window_hours": round(RATE_LIMIT_WINDOW_SECONDS / 3600, 1),
                "algorithm": "Sliding Window Log"
            }

class ConcurrencyGuard:
    """
    Guards server resources by limiting simultaneous graph stream executions.
    """
    def __init__(self, max_concurrent: int):
        self._max = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def is_saturated(self) -> bool:
        return self._semaphore.locked()

    async def acquire(self) -> bool:
        """Attempts to acquire execution slot immediately without queuing indefinitely."""
        try:
            # Wait up to 0.1s for a slot
            await asyncio.wait_for(self._semaphore.acquire(), timeout=0.1)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self):
        try:
            self._semaphore.release()
        except ValueError:
            pass

rate_limiter = SlidingWindowRateLimiter()
concurrency_guard = ConcurrencyGuard(MAX_CONCURRENT_RESEARCH)


# ==============================================================================
# 2. Input Validation & Prompt Injection Defense
# ==============================================================================
SUSPICIOUS_PATTERNS = [
    re.compile(r"(?i)(ignore\s+(all\s+|previous\s+|above\s+|prior\s+)*instructions)"),
    re.compile(r"(?i)(system\s+prompt)"),
    re.compile(r"(?i)(developer\s+message)"),
    re.compile(r"(?i)(\bjailbreak\b)"),
    re.compile(r"(?i)(\bDAN\s+mode\b)"),
    re.compile(r"(?i)(reveal\s+(the\s+|your\s+)*(prompt|instructions|secret|api|key))"),
    re.compile(r"(?i)(output\s+your\s+(prompt|instructions|system\s+message))"),
    re.compile(r"(?i)(you\s+are\s+now\s+(a\s+|an\s+)*(unrestricted|jailbroken|evil|unfiltered))"),
    re.compile(r"(?i)(\bexecute\s+command\b)"),
    re.compile(r"(?i)(\bcurl\s+https?://)"),
]

def validate_claim_input(task: str) -> str:
    """
    Validates and sanitizes user claim input:
    1. Checks length bounds (minimum 3 chars, maximum 500 chars).
    2. Strips adversarial control characters.
    3. Scans for prompt injection / jailbreak patterns.
    """
    if not task:
        raise ValueError("Claim text cannot be empty.")

    sanitized = task.strip()

    if len(sanitized) < 3:
        raise ValueError("Claim text is too short. Please provide at least 3 characters.")

    if len(sanitized) > MAX_INPUT_LENGTH:
        raise ValueError(
            f"Claim text exceeds maximum allowed limit of {MAX_INPUT_LENGTH} characters "
            f"(received {len(sanitized)} characters)."
        )

    # Scan for adversarial patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(sanitized):
            raise ValueError(
                "Security policy violation: Suspicious prompt injection or adversarial instruction detected."
            )

    # Neutralize XML / system-like tag injection
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")
    return sanitized


# ==============================================================================
# 3. Information Disclosure & Error Shielding
# ==============================================================================
SENSITIVE_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{8,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"lsv2_[a-zA-Z0-9_\-]{8,}"), "[REDACTED_LANGSMITH_KEY]"),
    (re.compile(r"[A-Za-z]:\\[^ \n\r\t]+"), "[INTERNAL_PATH]"),
    (re.compile(r"/app/[^ \n\r\t]+"), "[INTERNAL_PATH]"),
    (re.compile(r"tirenn-[a-zA-Z0-9_\-]+:[0-9]+"), "[INTERNAL_SERVICE]"),
    (re.compile(r"(postgres|redis|loki|chromadb):[0-9]+"), "[INTERNAL_SERVICE]"),
    (re.compile(r"\b172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+\b"), "[INTERNAL_IP]"),
    (re.compile(r"\b10\.\d+\.\d+\.\d+\b"), "[INTERNAL_IP]")
]

def shield_error(err: Exception) -> str:
    """
    Shields internal tracebacks, paths, and API keys from leaking to users.
    Returns sanitized, production-safe error explanation.
    """
    raw = str(err)

    # Known upstream error translation
    if "429" in raw or "rate limit" in raw.lower():
        return "Upstream AI service capacity exceeded. Please wait a moment before verifying another claim."
    if "401" in raw or "unauthorized" in raw.lower() or "authentication" in raw.lower():
        return "AI model provider authorization error. Please contact the administrator."
    if "timeout" in raw.lower():
        return "Network verification timed out while querying search or AI services. Please retry."

    # General redaction
    sanitized = raw
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # Truncate length
    if len(sanitized) > 200:
        sanitized = sanitized[:200] + "..."

    return f"Verification error: {sanitized}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enforces modern browser defense headers:
    - Content-Security-Policy (CSP)
    - X-Frame-Options (Clickjacking defense)
    - X-Content-Type-Options (MIME sniffing defense)
    - Referrer-Policy
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "img-src 'self' data: https:;"
        )
        return response
