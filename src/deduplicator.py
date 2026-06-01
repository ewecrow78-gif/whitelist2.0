"""
Умная дедупликация конфигов.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from src.models import VPNConfig

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Дедупликация по ключу: protocol + host + port + uuid.
    Среди дублей оставляет первый встреченный
    (или с наибольшим приоритетом источника).
    """

    SOURCE_PRIORITY: dict[str, int] = {
        "github": 3,
        "subscription": 2,
        "telegram": 1,
    }

    def __init__(self) -> None:
        self._seen: dict[str, VPNConfig] = {}
        self._stats: dict[str, int] = defaultdict(int)

    def add(self, cfg: VPNConfig) -> bool:
        """Добавляет конфиг. Возвращает True если он новый."""
        key = cfg.dedup_key
        if key in self._seen:
            self._stats["duplicates"] += 1
            return False
        if not cfg.host or cfg.port == 0:
            self._stats["invalid"] += 1
            return False
        self._seen[key] = cfg
        self._stats["unique"] += 1
        return True

    def add_many(self, configs: Iterable[VPNConfig]) -> int:
        """Добавляет много конфигов. Возвращает кол-во новых."""
        added = 0
        for cfg in configs:
            if self.add(cfg):
                added += 1
        return added

    @property
    def configs(self) -> list[VPNConfig]:
        return list(self._seen.values())

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def log_stats(self) -> None:
        logger.info(
            "Дедупликация: уникальных=%d, дублей=%d, невалидных=%d",
            self._stats.get("unique", 0),
            self._stats.get("duplicates", 0),
            self._stats.get("invalid", 0),
        )
