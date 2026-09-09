"""Execucao horaria: varre uma fatia rotativa de datas, grava historico e
dispara alertas quando (a) preco/pessoa < alvo ou (b) queda % sobre a media.

Rodar: python -m src.main
"""
from __future__ import annotations

import calendar
import logging
import random
import time
from datetime import date, timedelta

from . import analysis, flights, fx, notify
from .config import carregar
from .storage import agora_utc, carregar_estado, ler_historico, registrar, salvar_estado

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")


def unidades(cfg: dict) -> list[tuple[dict, dict]]:
    """Todas as combinacoes (rota, periodo), em ordem estavel."""
    return [(r, p) for p in cfg["periodos"] for r in cfg["rotas"]]


def combinacoes_datas(periodo: dict, cfg_viagem: dict, cfg_varre: dict) -> list[tuple[str, str, int]]:
    ano, mes = periodo["ano"], periodo["mes"]
    _, ndias = calendar.monthrange(ano, mes)
    dmin, dmax = cfg_viagem["dias_min"], cfg_viagem["dias_max"]
    n_volta = max(1, int(cfg_varre["amostras_volta"]))
    if n_volta == 1:
        duracoes = [(dmin + dmax) // 2]
    else:
        passo = (dmax - dmin) / (n_volta - 1)
        duracoes = sorted({int(round(dmin + i * passo)) for i in range(n_volta)})

    combos: list[tuple[str, str, int]] = []
    for dia in range(1, ndias + 1, int(cfg_varre["passo_dias_ida"])):
        ida = date(ano, mes, dia)
        for dur in duracoes:
            volta = ida + timedelta(days=dur)
            combos.append((ida.isoformat(), volta.isoformat(), dur))
    return combos


def main() -> None:
    cfg = carregar()
    estado = carregar_estado()
    historico = ler_historico()
    taxas = fx.cotacoes(cfg["moeda"]["fallback"])

    lista = unidades(cfg)
    cursor = int(estado.get("cursor", 0)) % len(lista)
    rota, periodo = lista[cursor]
    log.info("unidade %d/%d: %s-%s %s/%s", cursor + 1, len(lista),
             rota["origem"], rota["destino"], periodo["ano"], periodo["mes"])

    v = cfg["viagem"]
    combos = combinacoes_datas(periodo, v, cfg["varredura"])
    limite = int(cfg["varredura"]["max_consultas_por_run"])
    if len(combos) > limite:
        combos = random.sample(combos, limite)

    novas_linhas: list[dict] = []
    ofertas: list = []
    for data_ida, data_volta, _dur in combos:
        oferta = flights.buscar_mais_barata(
            origem=rota["origem"],
            destino=rota["destino"],
            data_ida=data_ida,
            data_volta=data_volta,
            adultos=v["passageiros_adultos"],
            criancas=v["passageiros_criancas"],
            classe=v["classe"],
            max_paradas=v["max_paradas"],
            taxas=taxas,
        )
        if oferta:
            ofertas.append(oferta)
            novas_linhas.append({
                "timestamp_utc": agora_utc(),
                "origem": oferta.origem,
                "destino": oferta.destino,
                "data_ida": oferta.data_ida,
                "data_volta": oferta.data_volta,
                "dias": oferta.dias,
                "preco_total_brl": oferta.preco_total_brl,
                "preco_por_pessoa_brl": oferta.preco_por_pessoa_brl,
                "moeda_origem": oferta.moeda_origem,
                "paradas": oferta.paradas,
                "companhia": oferta.companhia,
                "rotulo_google": oferta.rotulo_google,
            })
        time.sleep(float(cfg["varredura"]["pausa_entre_consultas_seg"]) + random.random())

    registrar(novas_linhas)
    log.info("%d consultas, %d ofertas coletadas", len(combos), len(ofertas))

    if not ofertas:
        _talvez_avisar_fonte_quebrada(estado)
    else:
        estado.pop("fonte_sem_dados_desde", None)

    _avaliar_alertas(cfg, estado, historico + novas_linhas, ofertas, taxas)

    estado["cursor"] = (cursor + 1) % len(lista)
    salvar_estado(estado)


def _avaliar_alertas(cfg, estado, historico, ofertas, taxas) -> None:
    alvo = float(cfg["precos"]["alvo_por_pessoa_brl"])
    queda = float(cfg["precos"]["queda_percentual"])
    dias_min_hist = float(cfg["precos"]["dias_minimos_historico"])
    janela = int(cfg["precos"]["media_movel_dias"])
    ultimo_alerta = estado["ultimo_alerta"]
    hist_dias = analysis.dias_de_historico(historico)

    for oferta in sorted(ofertas, key=lambda o: o.preco_por_pessoa_brl):
        # (a) alerta de alvo
        if oferta.preco_por_pessoa_brl < alvo and analysis.deve_alertar(oferta, "ALVO", ultimo_alerta):
            notify.telegram(_texto_alerta("ALVO ATINGIDO", oferta, alvo, None))
            notify.email(
                f"[Passagens] ALVO: {oferta.origem}-{oferta.destino} R$ "
                f"{oferta.preco_por_pessoa_brl:,.0f}/pessoa",
                _html_alerta("ALVO ATINGIDO", oferta, alvo, None),
                cfg["email"],
            )
            analysis.marcar_alerta(oferta, "ALVO", ultimo_alerta, agora_utc())
            continue

        # (b) alerta de queda percentual (so com historico suficiente)
        if hist_dias >= dias_min_hist:
            media, n = analysis.media_movel_por_pessoa(
                historico, oferta.origem, oferta.destino, janela
            )
            if media and n >= 5 and oferta.preco_por_pessoa_brl <= media * (1 - queda):
                if analysis.deve_alertar(oferta, "QUEDA", ultimo_alerta):
                    notify.telegram(_texto_alerta("QUEDA DE PRECO", oferta, alvo, media))
                    notify.email(
                        f"[Passagens] QUEDA: {oferta.origem}-{oferta.destino} "
                        f"-{(1 - oferta.preco_por_pessoa_brl / media) * 100:.0f}%",
                        _html_alerta("QUEDA DE PRECO", oferta, alvo, media),
                        cfg["email"],
                    )
                    analysis.marcar_alerta(oferta, "QUEDA", ultimo_alerta, agora_utc())


def _texto_alerta(titulo, oferta, alvo, media) -> str:
    link = flights.link_google_flights(
        oferta.origem, oferta.destino, oferta.data_ida, oferta.data_volta
    )
    linhas = [
        f"<b>\U0001F6A8 {titulo}</b>",
        f"{oferta.origem} → {oferta.destino}  ({oferta.dias} dias)",
        f"Ida {oferta.data_ida} | Volta {oferta.data_volta}",
        f"<b>R$ {oferta.preco_por_pessoa_brl:,.0f} por pessoa</b>  "
        f"(total 6 pax: R$ {oferta.preco_total_brl:,.0f})",
        f"{oferta.paradas} parada(s) | {oferta.companhia}",
        f"Alvo: R$ {alvo:,.0f}/pessoa",
    ]
    if media:
        linhas.append(
            f"Media da rota: R$ {media:,.0f}/pessoa "
            f"(↓ {(1 - oferta.preco_por_pessoa_brl / media) * 100:.0f}%)"
        )
    if oferta.rotulo_google:
        linhas.append(f"Google Flights: preco {oferta.rotulo_google}")
    linhas.append(f'\n<a href="{link}">Abrir no Google Flights</a>')
    linhas.append("\n⚠ Confirme preco, bagagem despachada e disponibilidade de 6 assentos no site antes de comprar.")
    return "\n".join(linhas)


def _html_alerta(titulo, oferta, alvo, media) -> str:
    return "<pre>" + _texto_alerta(titulo, oferta, alvo, media).replace("<b>", "").replace(
        "</b>", ""
    ).replace("<a href=\"", "").replace("\">Abrir no Google Flights</a>", "") + "</pre>"


def _talvez_avisar_fonte_quebrada(estado: dict) -> None:
    """Se nenhuma consulta retornar dados por varias execucoes seguidas,
    avisa uma vez por dia que a fonte pode ter quebrado."""
    from datetime import datetime, timezone

    agora = datetime.now(timezone.utc)
    desde = estado.get("fonte_sem_dados_desde")
    if not desde:
        estado["fonte_sem_dados_desde"] = agora.strftime("%Y-%m-%dT%H:%M:%SZ")
        return
    ultimo_aviso = estado.get("fonte_aviso_em")
    d0 = datetime.strptime(desde, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if (agora - d0).total_seconds() < 3 * 3600:
        return
    if ultimo_aviso:
        u = datetime.strptime(ultimo_aviso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if (agora - u).total_seconds() < 24 * 3600:
            return
    notify.telegram(
        "❗ <b>Agente de passagens</b>: nenhuma consulta retornou dados nas "
        "ultimas horas. A fonte (Google Flights via fast-flights) pode ter mudado "
        "ou estar bloqueando. Verificar os logs do GitHub Actions."
    )
    estado["fonte_aviso_em"] = agora.strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    main()
