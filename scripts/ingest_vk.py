#!/usr/bin/env python3
"""Собрать каталог методов VK API из официальной схемы VKCOM/vk-api-schema.

Схема лежит по разделам: <section>/methods.json. Берём только те разделы, что
нужны бизнесу (сообщество, товары, реклама, диалоги, статистика), остальное
(аудио, стикеры, подарки, игры) не тащим: каталог для продавца, не для клиента
соцсети.

    python3 scripts/ingest_vk.py --catalog vk_mcp/endpoints.yaml --apply

Аддитивно и идемпотентно: существующие записи (по operation_id) не трогаются,
поэтому выверенные вручную safety и keywords переживают повторный прогон.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

RAW = "https://raw.githubusercontent.com/VKCOM/vk-api-schema/master/{}/methods.json"

# Разделы и человеческие названия. Ключи совпадают с папками схемы.
SECTIONS: dict[str, str] = {
    "market": "Товары и магазин сообщества",
    "groups": "Сообщества",
    "ads": "Реклама (кабинет VK Ads)",
    "messages": "Диалоги и сообщения",
    "stats": "Статистика сообщества",
    "wall": "Записи на стене",
    "photos": "Фотографии и альбомы",
    "video": "Видео",
    "docs": "Документы",
    "board": "Обсуждения",
    "leadForms": "Лид-формы",
    "orders": "Заказы (VK Pay)",
    "storage": "Хранилище приложения",
    "utils": "Утилиты (ссылки, домены)",
    "users": "Пользователи",
    "donut": "VK Donut (подписки)",
    "prettyCards": "Карточки в записях",
    "podcasts": "Подкасты",
    "notifications": "Уведомления",
    "pages": "Вики-страницы",
}

# VK не размечает методы глаголами HTTP: всё это POST на /method/<name>.
# Единственный надёжный сигнал намерения — глагол в имени метода.
READ = re.compile(r"^(get|search|is|check|resolve)", re.I)
# Необратимое — только то, после чего данные не вернуть. `unban` и `restore`
# сюда НЕ входят: это откат чужого действия, он пишет, но ничего не теряет.
DESTRUCTIVE = re.compile(r"(^delete|^remove|^ban(?!ned)|Delete$|Remove$)")


def safety(name: str) -> str:
    """Класс доступа по имени метода. Порядок проверок важен.

    `groups.getBanned` читает, `groups.ban` пишет необратимо, и оба начинаются
    на одну букву: сначала отрабатывает точный DESTRUCTIVE, потом READ, потому
    что `deleteComment` не должен пройти как чтение из-за подстроки.
    """
    short = name.split(".", 1)[1] if "." in name else name
    if DESTRUCTIVE.search(short):
        return "destructive"
    if READ.match(short):
        return "read"
    return "write"


def summary_of(method: dict, name: str, human: str) -> str:
    """Описание метода, пригодное для поиска словами."""
    text = (method.get("description") or "").strip()
    if len(text) >= 15:
        return text[:300]
    return f"{human}: {name}" + (f". {text}" if text else "")


def snake(s: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s.replace(".", "_"))
    return re.sub(r"_+", "_", s).lower()


def fetch(section: str) -> list[dict]:
    with urllib.request.urlopen(RAW.format(section), timeout=60) as r:
        return json.load(r).get("methods", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    path = Path(a.catalog)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    rows: list[dict] = doc.get("endpoints", []) or []
    seen = {r["operation_id"] for r in rows}

    added = 0
    stats: Counter[str] = Counter()
    for section, human in SECTIONS.items():
        for m in fetch(section):
            name = m["name"]
            oid = "vk_" + snake(name)
            if oid in seen:
                continue
            params = [p["name"] for p in m.get("parameters", [])]
            row = {
                "operation_id": oid,
                "section": section,
                "method": "POST",
                "host": "api.vk.com",
                "path": f"/method/{name}",
                "scope": section,
                "safety": safety(name),
                # У части методов VK описания в схеме нет вовсе, а у части оно
                # в две буквы («Video»). Такая запись невидима для поиска по
                # каталогу, поэтому короткое описание достраиваем из раздела и
                # имени метода: «Товары и магазин сообщества: market.getOrderById».
                "summary": summary_of(m, name, human),
                "doc": f"https://dev.vk.com/method/{name}",
                # Курсорной пагинации у VK нет, везде offset/count.
                "pagination": "offset" if "offset" in params else "none",
            }
            if params:
                row["params"] = {"query": ", ".join(params[:12])}
            rows.append(row)
            seen.add(oid)
            added += 1
            stats[row["safety"]] += 1

    doc["default_host"] = "api.vk.com"
    doc["endpoints"] = rows
    print(f"new: {added} | catalog: {len(rows)}")
    print("safety:", dict(stats))
    if a.apply:
        path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        print("WRITTEN", path)


if __name__ == "__main__":
    main()
