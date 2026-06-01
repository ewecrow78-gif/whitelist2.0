"""
Запись результатов проверки в файлы конфигов.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.models import CheckResult, Protocol

logger = logging.getLogger(__name__)


class ResultWriter:
    """Записывает результаты в configs/."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.base = Path(cfg.get("paths", {}).get("configs_dir", "configs"))
        s = cfg.get("scoring", {})
        self.top_fast_count     = s.get("top_fast_count", 100)
        self.top_reliable_count = s.get("top_reliable_count", 100)
        self.best_ru_count      = s.get("best_ru_count", 100)
        self.base.mkdir(parents=True, exist_ok=True)
        (self.base / "countries").mkdir(exist_ok=True)
        (self.base / "protocols").mkdir(exist_ok=True)

    def write_all(self, results: list[CheckResult], all_configs_raw: list[str]) -> dict:
        """Записывает все выходные файлы. Возвращает статистику."""
        alive = [r for r in results if r.is_alive]
        alive_sorted = sorted(alive, key=lambda r: r.score, reverse=True)

        # all.txt — все собранные (сырые строки)
        self._write_lines(self.base / "all.txt", all_configs_raw)

        # alive.txt
        self._write_lines(self.base / "alive.txt", [r.config.raw for r in alive_sorted])

        # alive.json
        self._write_json(
            self.base / "alive.json",
            [r.to_dict() for r in alive_sorted]
        )

        # top_fast.txt — по min_latency
        top_fast = sorted(
            alive, key=lambda r: r.min_latency_ms
        )[:self.top_fast_count]
        self._write_lines(self.base / "top_fast.txt", [r.config.raw for r in top_fast])

        # top_reliable.txt — по success_rate, затем latency
        top_reliable = sorted(
            alive, key=lambda r: (-r.success_rate, r.latency_ms)
        )[:self.top_reliable_count]
        self._write_lines(self.base / "top_reliable.txt", [r.config.raw for r in top_reliable])

        # best_ru.txt — бонусные страны + лучший score
        ru_bonus = {"NL", "DE", "FI", "EE", "LV", "LT", "PL", "TR", "AE", "SE", "NO"}
        best_ru = sorted(
            [r for r in alive if r.config.country_code.upper() in ru_bonus],
            key=lambda r: r.score, reverse=True
        )[:self.best_ru_count]
        self._write_lines(self.base / "best_ru.txt", [r.config.raw for r in best_ru])

        # По странам
        by_country: dict[str, list[CheckResult]] = defaultdict(list)
        for r in alive_sorted:
            cc = r.config.country_code.upper() or "XX"
            by_country[cc].append(r)
        for cc, items in by_country.items():
            self._write_lines(
                self.base / "countries" / f"{cc}.txt",
                [r.config.raw for r in items]
            )

        # По протоколам
        by_proto: dict[str, list[CheckResult]] = defaultdict(list)
        for r in alive_sorted:
            by_proto[r.config.protocol.value].append(r)
        for proto, items in by_proto.items():
            self._write_lines(
                self.base / "protocols" / f"{proto}.txt",
                [r.config.raw for r in items]
            )

        stats = self._compute_stats(alive_sorted, all_configs_raw)
        logger.info(
            "Записано: всего=%d, живых=%d, top_fast=%d, top_reliable=%d, best_ru=%d",
            len(all_configs_raw), len(alive), len(top_fast), len(top_reliable), len(best_ru)
        )
        return stats

    def _compute_stats(
        self, alive: list[CheckResult], all_raw: list[str]
    ) -> dict:
        country_counter = Counter(
            r.config.country_code.upper() or "??" for r in alive
        )
        proto_counter = Counter(
            r.config.protocol.value for r in alive
        )
        latencies = [r.min_latency_ms for r in alive if r.min_latency_ms < 9000]
        return {
            "total": len(all_raw),
            "alive": len(alive),
            "top_countries": country_counter.most_common(10),
            "top_protocols": proto_counter.most_common(10),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "min_latency_ms": round(min(latencies), 1) if latencies else 0,
        }

    @staticmethod
    def _write_lines(path: Path, lines: list[str]) -> None:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.debug("Записан файл: %s (%d строк)", path, len(lines))

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.debug("Записан JSON: %s", path)
