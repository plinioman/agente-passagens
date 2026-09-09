"""Wrapper sobre a biblioteca fast-flights (Google Flights, sem chave de API).

Retorna, para um par (ida, volta), a opcao mais barata que respeite o limite
de paradas, com preco ja convertido para BRL.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from fast_flights import FlightData, Passengers, get_flights

from . import fx

log = logging.getLogger("flights")


@dataclass
class Oferta:
    origem: str
    destino: str
    data_ida: str
    data_volta: str
    dias: int
    preco_total_brl: float
    preco_por_pessoa_brl: float
    moeda_origem: str
    paradas: int
    companhia: str
    rotulo_google: str  # "low" | "typical" | "high" | ""


_MOEDAS = [
    ("R$", "BRL"),
    ("US$", "USD"),
    ("USD", "USD"),
    ("C$", "CAD"),
    ("CA$", "CAD"),
    ("CAD", "CAD"),
    ("€", "EUR"),
    ("EUR", "EUR"),
    ("$", "USD"),  # deixar por ultimo: fallback generico
]


def _parse_preco(texto: str) -> tuple[float, str] | None:
    """'R$ 4.321' -> (4321.0, 'BRL'); '$1,234' -> (1234.0, 'USD')."""
    if not texto:
        return None
    moeda = "USD"
    for simbolo, codigo in _MOEDAS:
        if simbolo in texto:
            moeda = codigo
            break
    digitos = re.sub(r"[^\d]", "", texto)
    if not digitos:
        return None
    return float(digitos), moeda


def _consultar(origem, destino, data_ida, data_volta, adultos, criancas, classe, max_paradas):
    """Uma tentativa. fetch_mode='local' usa Playwright (unico modo gratuito que
    ainda funciona: 'common' recebe pagina vazia e 'fallback' virou pago)."""
    return get_flights(
        flight_data=[
            FlightData(date=data_ida, from_airport=origem, to_airport=destino),
            FlightData(date=data_volta, from_airport=destino, to_airport=origem),
        ],
        trip="round-trip",
        seat=classe,
        passengers=Passengers(
            adults=adultos, children=criancas, infants_in_seat=0, infants_on_lap=0
        ),
        fetch_mode="local",
        max_stops=max_paradas,
    )


def buscar_mais_barata(
    origem: str,
    destino: str,
    data_ida: str,
    data_volta: str,
    adultos: int,
    criancas: int,
    classe: str,
    max_paradas: int,
    taxas: dict[str, float],
    tentativas: int = 2,
) -> Oferta | None:
    total_pax = adultos + criancas
    resultado = None
    for i in range(tentativas):
        try:
            resultado = _consultar(
                origem, destino, data_ida, data_volta, adultos, criancas, classe, max_paradas
            )
            break
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "consulta %s->%s %s/%s tentativa %d/%d: %s",
                origem, destino, data_ida, data_volta, i + 1, tentativas, str(exc)[:160],
            )
    if resultado is None:
        return None

    rotulo = getattr(resultado, "current_price", "") or ""
    voos = getattr(resultado, "flights", []) or []

    melhor: Oferta | None = None
    for voo in voos:
        paradas = getattr(voo, "stops", None)
        if paradas is None or paradas > max_paradas:
            continue
        parsed = _parse_preco(getattr(voo, "price", "") or "")
        if not parsed:
            continue
        valor, moeda = parsed
        if moeda == "BRL":
            total_brl = valor
        else:
            total_brl = fx.para_brl(valor, moeda, taxas)
        # O Google Flights mostra o total para todos os passageiros da busca.
        por_pessoa = round(total_brl / total_pax, 2)
        oferta = Oferta(
            origem=origem,
            destino=destino,
            data_ida=data_ida,
            data_volta=data_volta,
            dias=(_dias(data_ida, data_volta)),
            preco_total_brl=total_brl,
            preco_por_pessoa_brl=por_pessoa,
            moeda_origem=moeda,
            paradas=int(paradas),
            companhia=(getattr(voo, "name", "") or "")[:80],
            rotulo_google=rotulo,
        )
        if melhor is None or oferta.preco_por_pessoa_brl < melhor.preco_por_pessoa_brl:
            melhor = oferta
    return melhor


def _dias(data_ida: str, data_volta: str) -> int:
    from datetime import date

    a = date.fromisoformat(data_ida)
    b = date.fromisoformat(data_volta)
    return (b - a).days


def link_google_flights(origem: str, destino: str, data_ida: str, data_volta: str) -> str:
    q = f"Flights from {origem} to {destino} on {data_ida} returning {data_volta}"
    return "https://www.google.com/travel/flights?q=" + requests_quote(q)


def requests_quote(texto: str) -> str:
    from urllib.parse import quote

    return quote(texto)
