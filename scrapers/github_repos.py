"""
Скрапер GitHub-источников и прямых подписок.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import aiohttp

from scrapers.base import BaseScraper
from src.models import VPNConfig
from src.utils import decode_subscription, extract_configs_from_text, parse_uri

logger = logging.getLogger(__name__)


class GitHubScraper(BaseScraper):
    """Загружает конфиги из GitHub raw-ссылок и прямых подписок."""

    async def scrape(self) -> AsyncIterator[VPNConfig]:
        sources = (
            self.cfg.get("collection", {}).get("github_sources", [])
            + self.cfg.get("collection", {}).get("subscriptions", [])
        )
        for source in sources:
            url = source.get("url", "")
            fmt = source.get("format", "plain_list")
            if not url:
                continue
            self.logger.info("GitHub/Sub: %s", url)
            text = await self.fetch_text(url)
            if not text:
                continue
            lines = self._decode(text, fmt)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # plain_list может содержать несколько URI в строке
                for raw in extract_configs_from_text(line) or ([line] if "://" in line else []):
                    cfg = parse_uri(raw, source=f"github:{url}")
                    if cfg:
                        yield cfg

    def _decode(self, text: str, fmt: str) -> list[str]:
        if fmt in ("base64_sub", "base64_list"):
            decoded = decode_subscription(text)
            if decoded:
                return decoded
        return text.splitlines()
