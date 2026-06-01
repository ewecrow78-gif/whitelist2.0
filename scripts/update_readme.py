#!/usr/bin/env python3
"""
Генерация README.md на основе актуальной статистики.
Запуск: python -m scripts.update_readme
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FLAG_MAP = {
    "NL": "🇳🇱", "DE": "🇩🇪", "US": "🇺🇸", "FR": "🇫🇷", "GB": "🇬🇧",
    "FI": "🇫🇮", "SE": "🇸🇪", "NO": "🇳🇴", "PL": "🇵🇱", "TR": "🇹🇷",
    "EE": "🇪🇪", "LV": "🇱🇻", "LT": "🇱🇹", "AE": "🇦🇪", "SG": "🇸🇬",
    "JP": "🇯🇵", "KR": "🇰🇷", "HK": "🇭🇰", "UA": "🇺🇦", "RU": "🇷🇺",
    "CN": "🇨🇳", "IR": "🇮🇷", "CA": "🇨🇦", "AU": "🇦🇺", "CH": "🇨🇭",
    "AT": "🇦🇹", "BE": "🇧🇪", "CZ": "🇨🇿", "??": "🏴",
}
PROTO_EMOJI = {
    "vless": "⚡", "vmess": "🔷", "trojan": "🐴",
    "ss": "🔵", "ssr": "🔹", "hysteria2": "🚀",
    "hysteria": "💨", "tuic": "🌊", "unknown": "❓",
}

RAW_BASE = "https://raw.githubusercontent.com/YOUR_USERNAME/Gh0st_WhiteList/main/configs"


def load_stats(configs_dir: Path) -> dict:
    path = configs_dir / "stats.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def build_readme(stats: dict, configs_dir: Path) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total   = stats.get("total", 0)
    alive   = stats.get("alive", 0)
    avg_lat = stats.get("avg_latency_ms", 0)
    min_lat = stats.get("min_latency_ms", 0)
    alive_pct = round(alive / total * 100, 1) if total else 0

    # Таблица стран
    top_countries = stats.get("top_countries", [])
    countries_table = "| # | Флаг | Страна | Конфигов |\n|---|------|--------|----------|\n"
    for i, (cc, cnt) in enumerate(top_countries[:10], 1):
        flag = FLAG_MAP.get(cc, "🏴")
        countries_table += f"| {i} | {flag} | `{cc}` | **{cnt}** |\n"

    # Таблица протоколов
    top_protocols = stats.get("top_protocols", [])
    proto_table = "| # | Протокол | Конфигов | Доля |\n|---|----------|----------|------|\n"
    for i, (proto, cnt) in enumerate(top_protocols[:8], 1):
        emoji = PROTO_EMOJI.get(proto, "🔹")
        pct = round(cnt / alive * 100, 1) if alive else 0
        proto_table += f"| {i} | {emoji} `{proto}` | **{cnt}** | {pct}% |\n"

    # Подписки
    top_fast_cnt    = count_lines(configs_dir / "top_fast.txt")
    top_reliable_cnt = count_lines(configs_dir / "top_reliable.txt")
    best_ru_cnt     = count_lines(configs_dir / "best_ru.txt")

    readme = f"""<div align="center">

# 👻 Gh0st_WhiteList

**Элитный агрегатор и чекер VPN-конфигураций**

[![Configs](https://img.shields.io/badge/Всего_конфигов-{total}-blue?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0tMiAxNWwtNS01IDEuNDEtMS40MUwxMCAxNC4xN2w3LjU5LTcuNTlMMTkgOGwtOSA5eiIvPjwvc3ZnPg==)](configs/all.txt)
[![Alive](https://img.shields.io/badge/Живых-{alive}-brightgreen?style=for-the-badge)](configs/alive.txt)
[![Success Rate](https://img.shields.io/badge/Success_Rate-{alive_pct}%25-success?style=for-the-badge)](configs/alive.json)
[![Latency](https://img.shields.io/badge/Avg_Latency-{avg_lat}ms-orange?style=for-the-badge)](configs/top_fast.txt)
[![Updated](https://img.shields.io/badge/Обновлено-{now.replace(' ', '_').replace(':', '-')}-lightgrey?style=for-the-badge)](https://github.com/YOUR_USERNAME/Gh0st_WhiteList/actions)

> 🇷🇺 Оптимизировано для использования в России

</div>

---

## 📊 Статистика

<div align="center">

| Метрика | Значение |
|---------|----------|
| 📦 Всего собрано | **{total:,}** |
| ✅ Рабочих | **{alive:,}** ({alive_pct}%) |
| ⚡ Лучшая задержка | **{min_lat} мс** |
| 📈 Средняя задержка | **{avg_lat} мс** |
| 🕐 Обновлено | **{now}** |

</div>

---

## 🌍 Топ стран

{countries_table}

---

## 🔌 Протоколы

{proto_table}

---

## 🔗 Подписки

> Скопируй ссылку и вставь в клиент (v2rayN, Nekoray, Hiddify, Streisand и др.)

<div align="center">

| Подписка | Конфигов | Описание | Ссылка |
|----------|----------|----------|--------|
| 🚀 **Top Fast** | {top_fast_cnt} | Самые быстрые | [`top_fast.txt`]({RAW_BASE}/top_fast.txt) |
| 🛡️ **Top Reliable** | {top_reliable_cnt} | Самые стабильные | [`top_reliable.txt`]({RAW_BASE}/top_reliable.txt) |
| 🇷🇺 **Best RU** | {best_ru_cnt} | Лучшие для России | [`best_ru.txt`]({RAW_BASE}/best_ru.txt) |
| ✅ **All Alive** | {alive} | Все рабочие | [`alive.txt`]({RAW_BASE}/alive.txt) |
| 📦 **All** | {total} | Все собранные | [`all.txt`]({RAW_BASE}/all.txt) |

</div>

### 🔑 Подписки по протоколам

| Протокол | Ссылка |
|----------|--------|
| ⚡ VLESS | [`protocols/vless.txt`]({RAW_BASE}/protocols/vless.txt) |
| 🔷 VMess | [`protocols/vmess.txt`]({RAW_BASE}/protocols/vmess.txt) |
| 🐴 Trojan | [`protocols/trojan.txt`]({RAW_BASE}/protocols/trojan.txt) |
| 🔵 Shadowsocks | [`protocols/ss.txt`]({RAW_BASE}/protocols/ss.txt) |
| 🚀 Hysteria2 | [`protocols/hysteria2.txt`]({RAW_BASE}/protocols/hysteria2.txt) |

---

## 📱 Клиенты

| Платформа | Клиент |
|-----------|--------|
| 🪟 Windows | [v2rayN](https://github.com/2dust/v2rayN) · [Nekoray](https://github.com/MatsuriDayo/nekoray) |
| 🐧 Linux | [Nekoray](https://github.com/MatsuriDayo/nekoray) · [v2rayA](https://github.com/v2rayA/v2rayA) |
| 🍎 macOS | [Hiddify](https://github.com/hiddify/hiddify-next) · [V2Box](https://apps.apple.com/app/v2box-v2ray-tool/id6446814690) |
| 📱 Android | [Hiddify](https://github.com/hiddify/hiddify-next) · [v2rayNG](https://github.com/2dust/v2rayNG) |
| 🍏 iOS | [Streisand](https://apps.apple.com/app/streisand/id6450534064) · [Shadowrocket](https://apps.apple.com/app/shadowrocket/id932747118) |

---

## ⚙️ Как использовать

1. Скопируй ссылку нужной подписки из таблицы выше
2. Открой VPN-клиент → Добавить подписку → Вставь ссылку
3. Обнови подписку в клиенте
4. Подключайся к любому серверу из списка

---

## 🤖 Автообновление

Конфиги обновляются автоматически через **GitHub Actions** каждые **6 часов**.
