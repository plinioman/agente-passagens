"""Conversao de moeda para BRL usando AwesomeAPI (gratuita, sem chave)."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("fx")

URL = "https://economia.awesomeapi.com.br/last/USD-BRL,CAD-BRL,EUR-BRL"


def cotacoes(fallback: dict[str, float]) -> dict[str, float]:
    """Retorna {'USD': x, 'CAD': y, 'EUR': z, 'BRL': 1.0} em BRL por unidade."""
    taxas = {"BRL": 1.0}
    try:
        resp = requests.get(URL, timeout=15)
        resp.raise_for_status()
        dados = resp.json()
        for par, chave in (("USDBRL", "USD"), ("CADBRL", "CAD"), ("EURBRL", "EUR")):
            taxas[chave] = float(dados[par]["bid"])
        log.info("cambio ok: %s", taxas)
    except Exception as exc:  # noqa: BLE001
        log.warning("falha no cambio (%s); usando fallback", exc)
        for moeda, valor in fallback.items():
            taxas.setdefault(moeda, float(valor))
    # garante que todas as moedas conhecidas existam
    for moeda, valor in fallback.items():
        taxas.setdefault(moeda, float(valor))
    return taxas


def para_brl(valor: float, moeda: str, taxas: dict[str, float]) -> float:
    return round(valor * taxas.get(moeda, taxas.get("USD", 5.4)), 2)
