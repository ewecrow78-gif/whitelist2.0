"""
Скрапер подписок с поддержкой разных форматов.
Используется для URL-подписок не из GitHub.
"""
from __future__ import annotations

from typing import AsyncIterator

from scrapers.base import BaseScraper
from src.models import VPNConfig
from src.utils import decode_subscription, extract_configs_from_text, parse_uri


class SubscriptionScraper(BaseScraper):
    """Загружает и декодирует base64-подписки по URL."""

    async def scrape(self) -> AsyncIterator[VPNConfig]:
        subs = self.cfg.get("collection", {}).get("subscriptions", [])
        for sub in subs:
            url = sub.get("url", "")
            if not url:
                continue
            self.logger.info("Subscription: %s", url)
            text = await self.fetch_text(url)
            if not text:
                continue
            lines = decode_subscription(text)
            for line in lines:
                for raw in extract_configs_from_text(line) or ([line] if "://" in line else []):
                    cfg = parse_uri(raw, source=f"sub:{url}")
                    if cfg:
                        yield cfg
