"""In-memory sliding-window rate limits for the public (no login) credit check and chat (ADR 0006).

Per process: with several API replicas each counts on its own, so the real budgets are these numbers x replicas.
That is accepted for the demo; production needs shared counters or edge rate limiting (Front Door / APIM) and the
Azure OpenAI deployment quota as the hard cost ceiling.

Client key: see client_key (right-most public X-Forwarded-For hop; the left-most hop is client-controlled).
"""
from __future__ import annotations

import ipaddress
import os
import threading
import time
from collections import deque

MAX_KEYS = 10_000


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Too many requests; try again in {retry_after} s")
        self.retry_after = retry_after


class Limiter:
    def __init__(self, limit: int, window_s: float):
        self.limit, self.window = limit, window_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                if len(self._hits) >= MAX_KEYS:          # bounded memory and O(1) per request
                    self._purge(now)
                q = self._hits[key] = deque()
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise RateLimited(max(1, int(self.window - (now - q[0])) + 1))
            q.append(now)

    def _purge(self, now: float) -> None:
        """Forget idle keys; if all are active, drop the oldest half (an attacker rotating keys gains nothing over
        the global budget)."""
        for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
            del self._hits[k]
        if len(self._hits) >= MAX_KEYS:
            for k in list(self._hits)[:MAX_KEYS // 2]:
                del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


PER_IP = Limiter(int(os.environ.get("TRANSFERIQ_PUBLIC_PER_MIN", "20")), 60)                # checks + chat turns
AI_PER_IP = Limiter(int(os.environ.get("TRANSFERIQ_PUBLIC_AI_PER_IP_HOUR", "40")), 3600)    # model calls per client
AI_GLOBAL = Limiter(int(os.environ.get("TRANSFERIQ_PUBLIC_AI_PER_HOUR", "300")), 3600)      # model calls, all users


_INTERNAL = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
                                               "100.64.0.0/10", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10")]


def _public(hop: str) -> bool:
    try:
        ip = ipaddress.ip_address(hop)
    except ValueError:
        return False
    return not any(ip.version == n.version and ip in n for n in _INTERNAL)


def client_key(headers: dict, peer: str) -> str:
    """The right-most public address in X-Forwarded-For: the one our edge (Container Apps ingress) appended for
    the real client. Hops to its right are our own proxies (internal addresses); hops to its left were sent by the
    client and are ignored, so rotating a fake header gains nothing. A caller that skips nginx is still keyed on
    its own address, because the ingress appends it last."""
    hops = [h.strip() for h in (headers.get("x-forwarded-for") or "").split(",") if h.strip()]
    for hop in reversed(hops):
        if _public(hop):
            return hop
    return (hops[0] if hops else peer) or "unknown"


def ai_call(key: str) -> None:
    """One model call for client `key`: per-client budget first, so one client cannot spend everyone's."""
    AI_PER_IP.hit(key)
    AI_GLOBAL.hit("global")


def reset_all() -> None:
    PER_IP.reset()
    AI_PER_IP.reset()
    AI_GLOBAL.reset()
