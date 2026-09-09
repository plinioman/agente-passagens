"""Canais de notificacao: Telegram (obrigatorio) e e-mail SMTP (opcional)."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from .config import env

log = logging.getLogger("notify")


def telegram(texto: str) -> bool:
    token = env("TELEGRAM_TOKEN")
    chat_id = env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("TELEGRAM_TOKEN/CHAT_ID ausentes; pulando telegram")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("falha ao enviar telegram: %s", exc)
        return False


def email(assunto: str, corpo_html: str, cfg_email: dict) -> bool:
    if not cfg_email.get("ativo"):
        return False
    senha = env("SMTP_PASSWORD")
    if not senha:
        log.warning("SMTP_PASSWORD ausente; pulando e-mail")
        return False
    remetente = cfg_email["remetente"]
    destinatario = cfg_email["destinatario"]
    msg = MIMEText(corpo_html, "html", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    try:
        with smtplib.SMTP(cfg_email["smtp_host"], int(cfg_email["smtp_port"]), timeout=30) as s:
            s.starttls()
            s.login(remetente, senha)
            s.sendmail(remetente, [destinatario], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("falha ao enviar e-mail: %s", exc)
        return False
