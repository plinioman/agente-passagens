"""Carrega config.yaml e expoe como dicionario simples."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_CONFIG = RAIZ / "config.yaml"
CAMINHO_DADOS = RAIZ / "data"
CAMINHO_HISTORICO = CAMINHO_DADOS / "historico.csv"
CAMINHO_ESTADO = CAMINHO_DADOS / "estado.json"


def carregar() -> dict:
    with open(CAMINHO_CONFIG, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    CAMINHO_DADOS.mkdir(exist_ok=True)
    return cfg


def env(nome: str, padrao: str | None = None) -> str | None:
    valor = os.environ.get(nome, padrao)
    if valor is not None:
        valor = valor.strip()
    return valor or None
