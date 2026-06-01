"""
Скрапер Telegram-каналов через публичный веб-интерфейс (t.me/s/).
Не требует авторизации и Bot API.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncIterator

import aiohttp

from scrapers.base import BaseScraper
from src.models import VPNConfig
from src.utils import extract_configs_from_text, parse_uri

logger = logging.getLogger(__name__)

_POST_RE = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_BEFORE_RE = re.compile(r"&amp;|&lt;|&gt;|&quot;|&#39;|&#\d+;")
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'",
}


def _clean_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    for ent, ch in _HTML_ENTITIES.items():
        text = text.replace(ent, ch)
    return text


class TelegramScraper(BaseScraper):
    """Собирает конфиги из публичных Telegram-каналов."""

    BASE_URL = "https://t.me/s/{channel}"

    async def scrape(self) -> AsyncIterator[VPNConfig]:
        channels: list[str] = self.cfg.get("collection", {}).get("telegram_channels", [])
        sem = asyncio.Semaphore(
            self.cfg.get("collection", {}).get("max_concurrent_requests", 5)
        )
        tasks = [self._scrape_channel(ch, sem) for ch in channels]
        for coro in asyncio.as_completed(tasks):
            results = await coro
            for cfg in results:
                yield cfg

    async def _scrape_channel(
        self, channel: str, sem: asyncio.Semaphore
    ) -> list[VPNConfig]:
        async with sem:
            url = self.BASE_URL.format(channel=channel)
            self.logger.info("Telegram: @%s", channel)
            text = await self.fetch_text(url)
            if not text:
                return []
            configs: list[VPNConfig] = []
            for match in _POST_RE.finditer(text):
                post_html = match.group(1)
                post_text = _clean_html(post_html)
                for raw in extract_configs_from_text(post_text):
                    cfg = parse_uri(raw, source=f"telegram:@{channel}")
                    if cfg:
                        configs.append(cfg)
            self.logger.debug("@%s: найдено %d конфигов", channel, len(configs))
            return configs
