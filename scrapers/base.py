"""
Базовый класс скрапера.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import aiohttp

from src.models import VPNConfig


class BaseScraper(ABC):
    """Базовый скрапер. Все источники наследуются от него."""

    def __init__(self, cfg: dict, session: aiohttp.ClientSession) -> None:
        self.cfg = cfg
        self.session = session
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def scrape(self) -> AsyncIterator[VPNConfig]:
        """Генератор VPNConfig объектов."""
        ...

    async def fetch_text(self, url: str) -> str:
        """Загрузка текста с retry-логикой."""
        timeout = aiohttp.ClientTimeout(
            total=self.cfg.get("collection", {}).get("request_timeout", 30)
        )
        headers = {
            "User-Agent": self.cfg.get("collection", {}).get(
                "user_agent",
                "Mozilla/5.0"
            )
        }
        for attempt in range(3):
            try:
                async with self.session.get(
                    url, timeout=timeout, headers=headers,
                    ssl=False, allow_redirects=True
                ) as resp:
                    if resp.status == 200:
                        return await resp.text(encoding="utf-8", errors="ignore")
                    self.logger.debug("HTTP %d для %s", resp.status, url)
            except Exception as e:
                self.logger.debug("Попытка %d/%d для %s: %s", attempt + 1, 3, url, e)
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        return ""
