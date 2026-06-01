"""
GeoIP — определение страны по IP с кэшированием.
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_CACHE_FILE = Path("cache/geoip.json")
_RESOLVED_FILE = Path("cache/resolved_ips.json")


class GeoIPResolver:
    """
    Батч-резолвер: hostname → IP → (country_code, country_name).
    Использует ip-api.com (бесплатно, до 45 req/min или батчи до 100).
    """

    API_URL = "http://ip-api.com/batch"
    BATCH_SIZE = 100
    CACHE_TTL = 72 * 3600  # 72 часа

    def __init__(self, cache_ttl_hours: int = 72) -> None:
        self.cache_ttl = cache_ttl_hours * 3600
        self._geo_cache: dict[str, dict] = {}      # ip → geo
        self._dns_cache: dict[str, str] = {}       # host → ip
        self._load_caches()

    # ── Кэш ──────────────────────────────────────────────────────────────────

    def _load_caches(self) -> None:
        for path, attr in [(_CACHE_FILE, "_geo_cache"), (_RESOLVED_FILE, "_dns_cache")]:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    now = time.time()
                    # Убираем просроченные записи
                    setattr(self, attr, {
                        k: v for k, v in data.items()
                        if isinstance(v, dict) and now - v.get("_ts", 0) < self.cache_ttl
                        or isinstance(v, str)
                    })
                except Exception:
                    setattr(self, attr, {})

    def _save_caches(self) -> None:
        try:
            _CACHE_FILE.write_text(
                json.dumps(self._geo_cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _RESOLVED_FILE.write_text(
                json.dumps(self._dns_cache, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Не удалось сохранить кэш: %s", e)

    # ── Резолв DNS ────────────────────────────────────────────────────────────

    def _resolve_host(self, host: str) -> str:
        """Синхронный DNS-резолв с кэшем."""
        if host in self._dns_cache:
            return self._dns_cache[host]
        # Если уже IP — вернуть как есть
        import ipaddress
        try:
            ipaddress.ip_address(host)
            self._dns_cache[host] = host
            return host
        except ValueError:
            pass
        try:
            ip = socket.gethostbyname(host)
            self._dns_cache[host] = ip
            return ip
        except socket.gaierror:
            self._dns_cache[host] = ""
            return ""

    # ── API ───────────────────────────────────────────────────────────────────

    async def resolve_many(
        self,
        hosts: list[str],
        session: aiohttp.ClientSession,
    ) -> dict[str, dict[str, str]]:
        """
        Получает geo-данные для списка хостов.
        Возвращает словарь host → {"country_code": ..., "country_name": ...}.
        """
        result: dict[str, dict[str, str]] = {}
        ips_to_fetch: list[str] = []
        host_to_ip: dict[str, str] = {}

        for host in hosts:
            ip = self._resolve_host(host)
            host_to_ip[host] = ip
            if ip and ip not in self._geo_cache:
                ips_to_fetch.append(ip)

        # Батчевый запрос к ip-api
        for i in range(0, len(ips_to_fetch), self.BATCH_SIZE):
            batch = list(set(ips_to_fetch[i:i + self.BATCH_SIZE]))
            await self._fetch_batch(batch, session)
            await asyncio.sleep(1.5)  # Соблюдаем rate limit

        # Собираем результат
        for host, ip in host_to_ip.items():
            geo = self._geo_cache.get(ip, {})
            result[host] = {
                "country_code": geo.get("countryCode", "??"),
                "country_name": geo.get("country", "Unknown"),
                "ip": ip,
            }

        self._save_caches()
        return result

    async def _fetch_batch(
        self, ips: list[str], session: aiohttp.ClientSession
    ) -> None:
        payload = [{"query": ip, "fields": "countryCode,country,query"} for ip in ips]
        try:
            async with session.post(
                self.API_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data: list[dict[str, Any]] = await resp.json()
                    now = time.time()
                    for entry in data:
                        ip = entry.get("query", "")
                        if ip:
                            self._geo_cache[ip] = {**entry, "_ts": now}
        except Exception as e:
            logger.warning("GeoIP batch error: %s", e)
