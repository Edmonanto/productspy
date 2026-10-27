"""Fetch a public web page safely (competitor product pages from ad links).

Ad landing URLs come from third parties, so they are untrusted:
  * only http(s) on ports 80/443;
  * the host must resolve to public addresses only (no localhost, private,
    link-local, metadata or reserved ranges) — checked again on every redirect
    hop, so a redirect can't reach an internal service (SSRF);
  * at most 3 redirects, a 10 s timeout and 1.5 MB of body;
  * the text is returned as data — the caller never treats it as instructions.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 3


def _public_ip(addr: str) -> bool:
    ip = ipaddress.ip_address(addr)
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified or
                (ip.version == 6 and ip.ipv4_mapped is not None and not _public_ip(str(ip.ipv4_mapped))))


async def url_is_safe(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        return False
    if p.port not in (None, 80, 443):
        return False
    host = p.hostname
    try:
        ipaddress.ip_address(host)
        addrs = [host]
    except ValueError:
        if host.endswith((".local", ".internal", ".localhost")) or "." not in host:
            return False
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except OSError:
            return False
        addrs = list({i[4][0] for i in infos})
    return bool(addrs) and all(_public_ip(a) for a in addrs)


async def fetch_text(url: str, timeout: float = 10.0) -> Optional[tuple[str, str]]:
    """(final_url, text) or None. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=UA) as client:
            for _ in range(MAX_REDIRECTS + 1):
                if not await url_is_safe(url):
                    return None
                async with client.stream("GET", url) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                        url = urljoin(url, resp.headers["location"])
                        continue
                    if resp.status_code != 200:
                        return None
                    ctype = resp.headers.get("content-type", "")
                    if not any(t in ctype for t in ("text/html", "application/json", "text/plain")):
                        return None
                    buf = bytearray()
                    async for chunk in resp.aiter_bytes():
                        buf += chunk
                        if len(buf) > MAX_BYTES:
                            break
                    return url, buf.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        return None
    return None
