"""Relatorio programado (manha e tarde): melhores precos das ultimas 24h,
comparacao com a media da rota e variacao desde o relatorio anterior.

Rodar: python -m src.report
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import analysis, notify
from .config import carregar
from .storage import agora_utc, carregar_estado, ler_historico, salvar_estado

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("report")


def _ts(l: dict) -> datetime:
    return datetime.strptime(l["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def melhores_por_rota_data(historico: list[dict], desde_horas: int = 24) -> list[dict]:
    limite = datetime.now(timezone.utc) - timedelta(hours=desde_horas)
    recentes = [l for l in historico if l["preco_por_pessoa_brl"] and _ts(l) >= limite]
    melhor: dict[tuple, dict] = {}
    for l in recentes:
        chave = (l["origem"], l["destino"], l["data_ida"], l["data_volta"])
        preco = float(l["preco_por_pessoa_brl"])
        if chave not in melhor or preco < float(melhor[chave]["preco_por_pessoa_brl"]):
            melhor[chave] = l
    return sorted(melhor.values(), key=lambda l: float(l["preco_por_pessoa_brl"]))


def main() -> None:
    cfg = carregar()
    estado = carregar_estado()
    historico = ler_historico()
    top_n = int(cfg["relatorio"]["top_n"])
    alvo = float(cfg["precos"]["alvo_por_pessoa_brl"])
    janela = int(cfg["precos"]["media_movel_dias"])

    # So reporta rotas que estao atualmente configuradas em "buscas" (o
    # historico pode conter rotas antigas, ja descontinuadas, que nao devem
    # mais aparecer no relatorio).
    rotas_ativas = {(b["origem"], b["destino"]) for b in cfg["buscas"]}
    historico_ativo = [l for l in historico if (l["origem"], l["destino"]) in rotas_ativas]

    top = melhores_por_rota_data(historico_ativo)[:top_n]
    if not historico_ativo:
        notify.telegram("📊 Relatorio: ainda sem dados coletados. Aguarde as primeiras varreduras.")
        return

    snap_ant = (estado.get("snapshot_relatorio") or {}).get("itens", {})
    hist_dias = analysis.dias_de_historico(historico)

    linhas = [f"<b>📊 Relatorio de passagens</b> — {agora_utc()}",
              f"Alvo: R$ {alvo:,.0f}/pessoa | historico: {hist_dias:.1f} dias", ""]
    if not top:
        linhas.append("Nenhuma oferta coletada nas ultimas 24h.")
    novo_snap: dict[str, float] = {}
    for i, l in enumerate(top, 1):
        preco = float(l["preco_por_pessoa_brl"])
        chave = f'{l["origem"]}-{l["destino"]}|{l["data_ida"]}|{l["data_volta"]}'
        novo_snap[chave] = preco
        media, n = analysis.media_movel_por_pessoa(historico, l["origem"], l["destino"], janela)
        parte_media = f" | media rota R$ {media:,.0f}" if media else ""
        delta = ""
        if chave in snap_ant:
            d = preco - snap_ant[chave]
            if abs(d) >= 1:
                delta = f" | {'▲' if d > 0 else '▼'} R$ {abs(d):,.0f} vs. relatorio anterior"
        marca = " ✅" if preco < alvo else ""
        linhas.append(
            f"{i}. <b>{l['origem']}→{l['destino']}</b> {l['data_ida']}→{l['data_volta']} "
            f"({l['dias']}d) — <b>R$ {preco:,.0f}/pessoa</b>{marca}\n"
            f"   {l['paradas']} parada(s), {l['companhia']}{parte_media}{delta}"
        )

    texto = "\n".join(linhas)
    notify.telegram(texto)
    notify.email(f"[Passagens] Relatorio {datetime.now(timezone.utc):%d/%m %H:%MZ}",
                 "<pre>" + texto.replace("<b>", "").replace("</b>", "") + "</pre>", cfg["email"])

    estado["snapshot_relatorio"] = {"em": agora_utc(), "itens": novo_snap}
    salvar_estado(estado)


if __name__ == "__main__":
    main()
