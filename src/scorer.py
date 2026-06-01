"""
Система скоринга конфигов.
score = latency_score * w1 + stability_score * w2 + country_bonus * w3
"""
from __future__ import annotations

import logging
from typing import Any

from src.models import CheckResult

logger = logging.getLogger(__name__)


class ConfigScorer:
    """
    Вычисляет score для каждого CheckResult.
    Выше score → лучше конфиг.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        s = cfg.get("scoring", {})
        self.latency_weight: float   = s.get("latency_weight", 0.5)
        self.stability_weight: float = s.get("stability_weight", 0.35)
        self.country_weight: float   = s.get("country_bonus_weight", 0.15)
        self.bonus_countries: set[str] = set(s.get("bonus_countries", []))
        self.max_latency: float      = cfg.get("checker", {}).get("max_latency_ms", 5000.0)

    def score(self, result: CheckResult) -> float:
        """
        Возвращает score от 0.0 до 1.0.
        """
        if not result.is_alive:
            return 0.0

        # Latency score: 0 (медленно) → 1 (быстро)
        lat = min(result.latency_ms, self.max_latency)
        latency_score = 1.0 - (lat / self.max_latency)

        # Stability score = success_rate (0..1)
        stability_score = result.success_rate

        # Country bonus
        cc = result.config.country_code.upper()
        country_bonus = 1.0 if cc in self.bonus_countries else 0.0

        score = (
            latency_score   * self.latency_weight
            + stability_score * self.stability_weight
            + country_bonus   * self.country_weight
        )
        return round(min(score, 1.0), 6)

    def score_all(self, results: list[CheckResult]) -> list[CheckResult]:
        for r in results:
            r.score = self.score(r)
        return results
