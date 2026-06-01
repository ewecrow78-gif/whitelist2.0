#!/usr/bin/env python3
"""
Проверка собранных конфигов.
Запуск: python -m scripts.check
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checker.http_checker import HTTPChecker
from checker.result_writer import ResultWriter
from src.geo import GeoIPResolver
from src.models import VPNConfig
from src.scorer import ConfigScorer
from src.utils import load_config, parse_uri, setup_logging

logger = logging.getLogger("check")


async def main() -> None:
    cfg = load_config()
    setup_logging(
        cfg.get("logging", {}).get("level", "INFO"),
        cfg.get("logging", {}).get("file"),
    )
    logger.info("═" * 60)
    logger.info("Gh0st_WhiteList — Проверка конфигов")
    logger.info("═" * 60)

    configs_dir = Path(cfg.get("paths", {}).get("configs_dir", "configs"))
    all_path = configs_dir / "all.txt"

    if not all_path.exists():
        logger.error("Файл %s не найден! Сначала запусти collect.py", all_path)
        sys.exit(1)

    raw_lines = [
        l.strip() for l in all_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and "://" in l
    ]
    logger.info("Загружено %d конфигов для проверки", len(raw_lines))

    # Парсинг
    configs: list[VPNConfig] = []
    for line in raw_lines:
        parsed = parse_uri(line)
        if parsed:
            configs.append(parsed)
    logger.info("Успешно распарсено: %d", len(configs))

    # TCP-проверка
    checker = HTTPChecker(cfg)
    results = await checker.check_all(configs)

    alive = [r for r in results if r.is_alive]
    logger.info("Живых конфигов: %d / %d", len(alive), len(configs))

    # GeoIP для живых
    logger.info("Определение геолокации...")
    geo = GeoIPResolver(cfg.get("geoip", {}).get("cache_ttl_hours", 72))
    hosts = list({r.config.host for r in alive if r.config.host})
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        geo_data = await geo.resolve_many(hosts, session)

    for r in alive:
        info = geo_data.get(r.config.host, {})
        r.config.country_code = info.get("country_code", "??")
        r.config.country_name = info.get("country_name", "Unknown")
        r.config.ip = info.get("ip", "")

    # Скоринг
    scorer = ConfigScorer(cfg)
    scorer.score_all(results)

    # Запись результатов
    writer = ResultWriter(cfg)
    stats = writer.write_all(results, raw_lines)

    # Сохраняем статистику для README
    stats_path = configs_dir / "stats.json"
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Статистика сохранена в %s", stats_path)
    logger.info("Топ-страны: %s", stats.get("top_countries", [])[:5])
    logger.info("Топ-протоколы: %s", stats.get("top_protocols", [])[:5])
    logger.info("Готово! Средняя задержка: %.1f мс", stats.get("avg_latency_ms", 0))


if __name__ == "__main__":
    asyncio.run(main())
