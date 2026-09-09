# Agente de monitoramento de passagens aereas

Monitora precos de passagens **Belo Horizonte (CNF) → Nova York (JFK/EWR/LGA) ou Toronto (YYZ)**,
ida e volta, 8–12 dias, nos meses de marco a junho e setembro de 2027, para 6 passageiros
(3 adultos + 3 criancas), classe economica, ate 2 paradas.

Avisa por **Telegram** e **e-mail** quando o preco por pessoa fica abaixo de **R$ 4.000**
ou quando cai bem abaixo da media observada. Envia ainda **2 relatorios por dia**
(08:00 e 15:00 BRT).

Custo: **R$ 0** — roda em GitHub Actions (repo privado, dentro da cota gratuita).

## Como funciona

| Peca | O que faz |
|---|---|
| `.github/workflows/scan.yml` | A cada hora (`cron`), roda `python -m src.main` |
| `.github/workflows/report.yml` | As 11:00 e 18:00 UTC, roda `python -m src.report` |
| `src/flights.py` | Consulta o Google Flights via biblioteca `fast-flights` (sem chave) |
| `src/fx.py` | Converte USD/CAD/EUR → BRL (AwesomeAPI, gratuita) |
| `src/analysis.py` | Media movel por rota e regras de alerta (com anti-spam) |
| `src/notify.py` | Envio por Telegram e SMTP |
| `data/historico.csv` | Historico de precos, commitado de volta pelo proprio workflow |
| `data/estado.json` | Cursor da varredura rotativa, ultimos alertas, snapshot do relatorio |

A varredura e **rotativa**: cada execucao cobre uma combinacao (rota × mes).
Com 4 rotas × 5 meses = 20 combinacoes, o ciclo completo leva ~20 horas.
Isso mantem cada execucao curta e evita bloqueio da fonte.

## Configuracao (uma vez)

1. **Secrets** em `Settings → Secrets and variables → Actions`:
   - `TELEGRAM_TOKEN` — token do bot criado no @BotFather
   - `TELEGRAM_CHAT_ID` — id do seu chat com o bot
   - `SMTP_PASSWORD` — App Password do Gmail (16 caracteres, conta com 2FA)
2. Ajuste `config.yaml` se quiser (rotas, meses, alvo, % de queda).
3. Rode o workflow **scan** manualmente (aba Actions → scan → Run workflow) para testar.

## Limitacoes conhecidas

- `fast-flights` faz scraping nao-oficial do Google Flights: pode quebrar sem aviso.
  O agente manda um alerta no Telegram se ficar horas sem coletar nada.
- O preco coletado e o exibido pelo Google Flights (total dos 6 passageiros ÷ 6).
  **Sempre confirmar preco, bagagem despachada e disponibilidade de 6 assentos no site
  antes de comprar.**
- `cron` do GitHub Actions e "melhor esforco": pode atrasar 5–20 min.

## Roadmap

- Fase 2: relatorio por e-mail mais rico + ajuste fino da media movel.
- Fase 3: camada de confirmacao precisa (bagagem, 6 assentos) via Amadeus Self-Service.
- Fase 4: seed inicial de historico e leitura de "quao realista e o alvo".
