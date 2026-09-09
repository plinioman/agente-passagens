"""Media movel e decisao de alertas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean


def _ts(linha: dict) -> datetime:
    return datetime.strptime(linha["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def media_movel_por_pessoa(
    historico: list[dict], origem: str, destino: str, janela_dias: int
) -> tuple[float | None, int]:
    """Media do menor preco/pessoa observado para a rota na janela. Retorna
    (media, qtd_amostras)."""
    limite = datetime.now(timezone.utc) - timedelta(days=janela_dias)
    valores = [
        float(l["preco_por_pessoa_brl"])
        for l in historico
        if l["origem"] == origem
        and l["destino"] == destino
        and l["preco_por_pessoa_brl"]
        and _ts(l) >= limite
    ]
    if not valores:
        return None, 0
    return round(mean(valores), 2), len(valores)


def dias_de_historico(historico: list[dict]) -> float:
    if not historico:
        return 0.0
    tss = [_ts(l) for l in historico if l.get("timestamp_utc")]
    if not tss:
        return 0.0
    return (max(tss) - min(tss)).total_seconds() / 86400.0


def chave_alerta(oferta) -> str:
    return f"{oferta.origem}-{oferta.destino}|{oferta.data_ida}|{oferta.data_volta}"


def deve_alertar(
    oferta,
    tipo: str,
    ultimo_alerta: dict,
    horas_silencio: int = 12,
    reincidir_se_cair: float = 0.05,
) -> bool:
    """Anti-spam: nao repete o mesmo alerta (rota+datas+tipo) dentro de
    `horas_silencio`, a menos que o preco tenha caido mais `reincidir_se_cair`."""
    chave = f"{tipo}:{chave_alerta(oferta)}"
    anterior = ultimo_alerta.get(chave)
    if not anterior:
        return True
    try:
        ts_ant = datetime.strptime(anterior["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        preco_ant = float(anterior["preco_pp"])
    except (KeyError, ValueError, TypeError):
        return True
    if datetime.now(timezone.utc) - ts_ant >= timedelta(hours=horas_silencio):
        return True
    if oferta.preco_por_pessoa_brl <= preco_ant * (1 - reincidir_se_cair):
        return True
    return False


def marcar_alerta(oferta, tipo: str, ultimo_alerta: dict, quando: str) -> None:
    chave = f"{tipo}:{chave_alerta(oferta)}"
    ultimo_alerta[chave] = {"ts": quando, "preco_pp": oferta.preco_por_pessoa_brl}
