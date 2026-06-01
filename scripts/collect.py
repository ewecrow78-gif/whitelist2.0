#!/usr/bin/env python3
"""
Сбор VPN-конфигов из всех источников.
Запуск: python -m scripts.collect
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import aiohttp

# Добавляем корень в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.github_repos import GitHubScraper
from scrapers.telegram import TelegramScraper
from src.deduplicator import Deduplicator
from src.utils import load_config, setup_logging

logger = logging.getLogger("collect")


async def main() -> None:
    cfg = load_config()
    setup_logging(
        cfg.get("logging", {}).get("level", "INFO"),
        cfg.get("logging", {}).get("file"),
    )
    logger.info("═" * 60)
    logger.info("Gh0st_WhiteList — Сбор конфигов")
    logger.info("═" * 60)

    dedup = Deduplicator()
    out_dir = Path(cfg.get("paths", {}).get("configs_dir", "configs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    connector = aiohttp.TCPConnector(ssl=False, limit=30)
    async with aiohttp.ClientSession(connector=connector) as session:
        scrapers = [
            TelegramScraper(cfg, session),
            GitHubScraper(cfg, session),
        ]
        for scraper in scrapers:
            logger.info("Запуск: %s", scraper.__class__.__name__)
            async for vpn_cfg in scraper.scrape():
                dedup.add(vpn_cfg)

    dedup.log_stats()
    configs = dedup.configs
    logger.info("Итого уникальных конфигов: %d", len(configs))

    # Сохраняем all.txt
    all_path = out_dir / "all.txt"
    all_path.write_text(
        "\n".join(c.raw for c in configs) + "\n", encoding="utf-8"
    )
    logger.info("Сохранено в %s", all_path)


if __name__ == "__main__":
    asyncio.run(main())
