"""
Вспомогательные утилиты: парсинг URI, base64, логирование.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Iterator

import colorlog
import yaml

from src.models import Protocol, VPNConfig

# ── Логирование ──────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Настройка цветного логирования."""
    fmt = "%(log_color)s%(asctime)s%(reset)s | %(log_color)s%(levelname)-8s%(reset)s | %(name)s | %(message)s"
    handler = colorlog.StreamHandler(sys.stdout)
    handler.setFormatter(colorlog.ColoredFormatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
        root.addHandler(fh)

    return root


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Base64 ────────────────────────────────────────────────────────────────────

def safe_b64decode(data: str) -> str:
    """Безопасное декодирование base64."""
    if not data or not isinstance(data, str):
        return ""
    data = data.strip()
    if not data:
        return ""

    # Добавляем padding
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding

    try:
        return base64.b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def decode_subscription(raw: str) -> list[str]:
    """Декодирует base64-подписку → список строк."""
    decoded = safe_b64decode(raw)
    if not decoded:
        decoded = raw  # fallback на plain text
    lines = [l.strip() for l in decoded.splitlines() if l.strip()]
    return lines

# ── Парсинг URI ───────────────────────────────────────────────────────────────

_PROTO_RE = re.compile(
    r"^(vless|vmess|trojan|ss|ssr|hysteria2?|tuic)://", re.IGNORECASE
)


def extract_configs_from_text(text: str) -> Iterator[str]:
    """Извлекает все URI конфигов из произвольного текста."""
    # Ищем по префиксам протоколов
    pattern = re.compile(
        r"(vless|vmess|trojan|ss|ssr|hysteria2?|tuic)://[^\s\"\'<>\u0000-\u001F]+",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        yield m.group(0).rstrip(".,;)")


def parse_uri(raw: str, source: str = "") -> VPNConfig | None:
    """Парсит URI → VPNConfig. Возвращает None при ошибке."""
    raw = raw.strip()
    m = _PROTO_RE.match(raw)
    if not m:
        return None
    proto_str = m.group(1).lower()
    proto = Protocol(proto_str) if proto_str in Protocol._value2member_map_ else Protocol.UNKNOWN

    try:
        if proto == Protocol.VMESS:
            return _parse_vmess(raw, source)
        elif proto in (Protocol.VLESS, Protocol.TROJAN):
            return _parse_vless_trojan(raw, proto, source)
        elif proto == Protocol.SS:
            return _parse_ss(raw, source)
        else:
            return _parse_generic(raw, proto, source)
    except Exception:
        return None


def _parse_vmess(raw: str, source: str) -> VPNConfig | None:
    b64 = raw[len("vmess://"):]
    decoded = safe_b64decode(b64)
    if not decoded:
        return None
    try:
        data = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    return VPNConfig(
        raw=raw,
        protocol=Protocol.VMESS,
        host=str(data.get("add", data.get("host", ""))),
        port=data.get("port", 0),
        uuid=str(data.get("id", "")),
        remark=str(data.get("ps", data.get("remarks", ""))),
        source=source,
    )


def _parse_vless_trojan(raw: str, proto: Protocol, source: str) -> VPNConfig | None:
    # vless://uuid@host:port?params#remark
    try:
        without_scheme = raw.split("://", 1)[1]
        # Отделяем fragment (remark)
        remark = ""
        if "#" in without_scheme:
            without_scheme, remark = without_scheme.rsplit("#", 1)
            remark = urllib.parse.unquote(remark)
        # uuid@host:port
        if "@" not in without_scheme:
            return None
        uid_part, hostport = without_scheme.rsplit("@", 1)
        uid = uid_part.split("?")[0]
        hostport = hostport.split("?")[0]
        host, port_str = _split_host_port(hostport)
        return VPNConfig(
            raw=raw,
            protocol=proto,
            host=host,
            port=int(port_str) if port_str.isdigit() else 0,
            uuid=uid,
            remark=remark,
            source=source,
        )
    except Exception:
        return None


def _parse_ss(raw: str, source: str) -> VPNConfig | None:
    try:
        without_scheme = raw[len("ss://"):]
        remark = ""
        if "#" in without_scheme:
            without_scheme, remark = without_scheme.rsplit("#", 1)
            remark = urllib.parse.unquote(remark)
        # Может быть base64 или userinfo@host:port
        if "@" in without_scheme:
            b64_part, hostport = without_scheme.rsplit("@", 1)
            hostport = hostport.split("?")[0]
            host, port_str = _split_host_port(hostport)
            decoded_uid = safe_b64decode(b64_part) or b64_part
        else:
            decoded = safe_b64decode(without_scheme)
            if not decoded or "@" not in decoded:
                return None
            uid_part, hostport = decoded.rsplit("@", 1)
            hostport = hostport.split("?")[0]
            host, port_str = _split_host_port(hostport)
            decoded_uid = uid_part
        return VPNConfig(
            raw=raw,
            protocol=Protocol.SS,
            host=host,
            port=int(port_str) if port_str.isdigit() else 0,
            uuid=decoded_uid,
            remark=remark,
            source=source,
        )
    except Exception:
        return None


def _parse_generic(raw: str, proto: Protocol, source: str) -> VPNConfig | None:
    try:
        without_scheme = raw.split("://", 1)[1]
        remark = ""
        if "#" in without_scheme:
            without_scheme, remark = without_scheme.rsplit("#", 1)
        if "@" in without_scheme:
            uid_part, hostport = without_scheme.rsplit("@", 1)
            hostport = hostport.split("?")[0]
            host, port_str = _split_host_port(hostport)
            return VPNConfig(
                raw=raw, protocol=proto, host=host,
                port=int(port_str) if port_str.isdigit() else 0,
                uuid=uid_part, remark=urllib.parse.unquote(remark),
                source=source,
            )
        return VPNConfig(raw=raw, protocol=proto, source=source)
    except Exception:
        return None


def _split_host_port(hostport: str) -> tuple[str, str]:
    """Разделяет host:port, учитывая IPv6."""
    if hostport.startswith("["):
        # IPv6
        idx = hostport.index("]")
        host = hostport[1:idx]
        port = hostport[idx + 2:] if idx + 2 < len(hostport) else "0"
    elif ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, "0"
    return host.strip(), port.strip()
