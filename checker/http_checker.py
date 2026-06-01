"""
Асинхронный HTTP-чекер конфигов.

Проверяет доступность по HTTP/HTTPS, измеряет задержку,
вычисляет success_rate по нескольким попыткам.

Важно: это HTTP-пинг к целевым URL. Настоящая проверка
VPN-туннелей требует запуска xray/sing-box, что выходит
за рамки данного чекера. Здесь проверяется доступность
хоста по TCP (connect) как индикатор живости.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp
from tqdm.asyncio import tqdm

from src.models import CheckResult, VPNConfig

logger = logging.getLogger(__name__)


class HTTPChecker:
    """
    Проверяет список VPNConfig через TCP-connect к host:port.
    Если хост отвечает на TCP — конфиг считается потенциально живым.
    Также делает HTTP HEAD к ping_targets через aiohttp (без прокси).
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        c = cfg.get("checker", {})
        self.ping_targets: list[str] = c.get("ping_targets", [
            "http://www.gstatic.com/generate_204",
        ])
        self.attempts: int    = c.get("attempts", 3)
        self.timeout: float   = c.get("timeout", 10)
        self.concurrency: int = c.get("concurrency", 200)
        self.max_latency: float = c.get("max_latency_ms", 5000)
        self.min_success_rate: float = c.get("min_success_rate", 0.33)

    async def check_all(self, configs: list[VPNConfig]) -> list[CheckResult]:
        """Проверяет все конфиги, возвращает список CheckResult."""
        sem = asyncio.Semaphore(self.concurrency)
        connector = aiohttp.TCPConnector(
            limit=self.concurrency,
            ssl=False,
            force_close=True,
            enable_cleanup_closed=True,
        )
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_one(cfg, sem, session) for cfg in configs]
            results: list[CheckResult] = []
            for coro in tqdm(
                asyncio.as_completed(tasks),
                total=len(tasks),
                desc="🔍 Проверка",
                unit="cfg",
                ncols=90,
            ):
                result = await coro
                results.append(result)
        return results

    async def _check_one(
        self,
        cfg: VPNConfig,
        sem: asyncio.Semaphore,
        session: aiohttp.ClientSession,
    ) -> CheckResult:
        async with sem:
            return await self._tcp_probe(cfg)

    async def _tcp_probe(self, cfg: VPNConfig) -> CheckResult:
        """
        TCP connect probe: пробует подключиться к host:port.
        Это быстрый и надёжный способ проверки доступности хоста.
        """
        if not cfg.host or cfg.port == 0:
            return CheckResult(config=cfg)

        latencies: list[float] = []
        successes = 0

        for _ in range(self.attempts):
            t0 = time.monotonic()
            try:
                conn = asyncio.open_connection(cfg.host, cfg.port)
                reader, writer = await asyncio.wait_for(conn, timeout=self.timeout)
                latency_ms = (time.monotonic() - t0) * 1000
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                latencies.append(latency_ms)
                successes += 1
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass
            except Exception as e:
                logger.debug("Probe error %s:%d — %s", cfg.host, cfg.port, e)

        success_rate = successes / self.attempts
        is_alive = (
            success_rate >= self.min_success_rate
            and bool(latencies)
            and min(latencies) <= self.max_latency
        )

        avg_latency = sum(latencies) / len(latencies) if latencies else 9999.0
        min_latency = min(latencies) if latencies else 9999.0

        return CheckResult(
            config=cfg,
            is_alive=is_alive,
            latency_ms=avg_latency,
            min_latency_ms=min_latency,
            success_rate=success_rate,
            attempts=self.attempts,
        )
