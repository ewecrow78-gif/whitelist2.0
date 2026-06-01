"""
Pydantic-модели для конфигов и результатов проверки.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator


class Protocol(str, Enum):
    VLESS   = "vless"
    VMESS   = "vmess"
    TROJAN  = "trojan"
    SS      = "ss"
    SSR     = "ssr"
    HYSTERIA = "hysteria"
    HYSTERIA2 = "hysteria2"
    TUIC    = "tuic"
    UNKNOWN = "unknown"


class VPNConfig(BaseModel):
    """Распарсенный VPN-конфиг."""
    raw: str                          # Оригинальная строка
    protocol: Protocol = Protocol.UNKNOWN
    host: str = ""
    port: int = 0
    uuid: str = ""                    # uuid / password / psk
    remark: str = ""
    source: str = ""                  # откуда собран

    # Заполняется после GeoIP
    country_code: str = ""
    country_name: str = ""
    ip: str = ""

    @property
    def dedup_key(self) -> str:
        """Ключ дедупликации: protocol+host+port+uuid."""
        raw_key = f"{self.protocol}|{self.host.lower()}|{self.port}|{self.uuid}"
        return hashlib.md5(raw_key.encode()).hexdigest()

    @field_validator("port", mode="before")
    @classmethod
    def coerce_port(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


class CheckResult(BaseModel):
    """Результат проверки одного конфига."""
    config: VPNConfig
    is_alive: bool = False
    latency_ms: float = 9999.0        # средняя задержка
    min_latency_ms: float = 9999.0
    success_rate: float = 0.0         # доля успешных попыток
    attempts: int = 0
    score: float = 0.0                # итоговый скор (выше = лучше)

    def to_dict(self) -> dict:
        return {
            "raw": self.config.raw,
            "protocol": self.config.protocol,
            "host": self.config.host,
            "port": self.config.port,
            "country_code": self.config.country_code,
            "country_name": self.config.country_name,
            "ip": self.config.ip,
            "is_alive": self.is_alive,
            "latency_ms": round(self.latency_ms, 1),
            "min_latency_ms": round(self.min_latency_ms, 1),
            "success_rate": round(self.success_rate, 3),
            "score": round(self.score, 4),
            "source": self.config.source,
        }
