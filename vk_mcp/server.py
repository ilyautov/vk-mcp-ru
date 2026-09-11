#!/usr/bin/env python3
"""vk_mcp — MCP-сервер для VK API (бизнес-разделы).

Каталог собран из официальной схемы VKCOM/vk-api-schema: 373 метода по
сообществам, товарам, рекламе, диалогам, статистике и лид-формам. Разделы,
которые нужны не бизнесу, а пользователю соцсети (аудио, подарки, стикеры),
в каталог не тащим осознанно.

Авторизация: сервисный или пользовательский токен, `Authorization: Bearer`.
Версию API VK требует в каждом запросе, параметр `v`, он подставляется
автоматически в `default_query`.

Запуск:
    VK_TOKEN=... python -m vk_mcp.server
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from schema_mcp_core.client import MarketplaceClient, ServiceConfig
from schema_mcp_core.entities import EntityIndex
from schema_mcp_core.registry import Catalog
from schema_mcp_core.tools import register_cabinet_tools, register_generic_tools
from schema_mcp_core.transport import run as run_transport

CATALOG_PATH = Path(__file__).with_name("endpoints.yaml")

# Версия VK API. Меняется редко, но менять надо осознанно: старая версия молча
# отдаёт другой формат ответа, а не ошибку.
VK_API_VERSION = "5.199"


def _build_headers(creds: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {creds.get('token', '')}"}


VK_CONFIG = ServiceConfig(
    name="vk",
    scheme="https",
    fields=["token"],
    env_map={"token": "VK_TOKEN"},
    build_headers=_build_headers,
    allowed_host_suffixes=[".vk.com", "api.vk.com"],
)

mcp = FastMCP("vk-mcp-ru")
entities = EntityIndex.load()
catalog = Catalog.from_yaml(CATALOG_PATH, entities=entities)
client = MarketplaceClient(VK_CONFIG)

register_generic_tools(
    mcp, svc="vk", client=client, catalog=catalog, entities=entities,
    key_help=f"dev.vk.com → приложение → сервисный ключ доступа, либо токен "
             f"сообщества с нужными правами. Все вызовы идут с v={VK_API_VERSION}.",
)
register_cabinet_tools(mcp, svc="vk", client=client, catalog=catalog)


def main() -> None:
    run_transport(mcp)


def cli() -> None:
    """Точка входа пакета: без аргументов сервер, с `doctor` диагностика."""
    import sys

    args = sys.argv[1:]
    if args and args[0] == "doctor":
        from schema_mcp_core.doctor import main as doctor_main

        raise SystemExit(doctor_main([("vk", "VK API",
                                       "vk_mcp.server")], args[1:], "vk-mcp-ru"))
    if args:
        print(f"vk-mcp-ru: неизвестный аргумент {args[0]!r} (есть только 'doctor')",
              file=sys.stderr)
        raise SystemExit(2)
    main()


if __name__ == "__main__":
    main()
