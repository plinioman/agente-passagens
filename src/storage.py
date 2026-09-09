"""Persistencia: historico.csv (append) + estado.json (cursor, alertas, snapshots).

Ambos ficam em data/ e sao commitados de volta pelo workflow, servindo de
banco de dados gratuito e versionado.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import CAMINHO_ESTADO, CAMINHO_HISTORICO

COLUNAS = [
    "timestamp_utc",
    "origem",
    "destino",
    "data_ida",
    "data_volta",
    "dias",
    "preco_total_brl",
    "preco_por_pessoa_brl",
    "moeda_origem",
    "paradas",
    "companhia",
    "rotulo_google",
]


def agora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def registrar(linhas: list[dict]) -> None:
    if not linhas:
        return
    caminho = Path(CAMINHO_HISTORICO)
    novo = not caminho.exists()
    with open(caminho, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUNAS)
        if novo:
            writer.writeheader()
        for linha in linhas:
            writer.writerow({c: linha.get(c, "") for c in COLUNAS})


def ler_historico() -> list[dict]:
    caminho = Path(CAMINHO_HISTORICO)
    if not caminho.exists():
        return []
    with open(caminho, "r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def carregar_estado() -> dict:
    caminho = Path(CAMINHO_ESTADO)
    if not caminho.exists():
        return {"cursor": 0, "ultimo_alerta": {}, "snapshot_relatorio": None}
    with open(caminho, "r", encoding="utf-8") as fh:
        estado = json.load(fh)
    estado.setdefault("cursor", 0)
    estado.setdefault("ultimo_alerta", {})
    estado.setdefault("snapshot_relatorio", None)
    return estado


def salvar_estado(estado: dict) -> None:
    with open(CAMINHO_ESTADO, "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)
