# Agente de monitoramento de passagens aereas

Monitora o preco do trecho domestico **Belo Horizonte (CNF) <-> Rio de Janeiro (GIG)**,
nas datas fixas **28/04/2027** (ida) e **11/05/2027** (volta) — a conexao para encaixar
com o voo internacional GIG-JFK-GIG ja comprado — para 6 passageiros (3 adultos + 3
criancas), classe economica.

Avisa por **Telegram** e **e-mail** quando o preco por pessoa fica abaixo de **R$ 500**
(configuravel em `config.yaml`). Envia ainda **2 relatorios por dia** (08:00 e 15:00 BRT).

Custo: **R$ 0** — roda em GitHub Actions (repo publico, minutos ilimitados).

> Historico anterior: o agente comecou monitorando CNF -> Nova York/Toronto para a
> viagem internacional. Essa parte ja foi comprada (GIG-JFK direto, R$ 22.492,58 para
> os 6, com bagagem), entao o foco mudou para o trecho de conexao. O historico antigo
> continua em `data/historico.csv` como registro, mas nao e mais coletado.

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
| `data/estado.json` | Ultimos alertas disparados e snapshot do relatorio anterior |

`config.yaml` tem uma lista `buscas:` com a(s) rota(s) e datas fixas monitoradas —
hoje so CNF-GIG, mas da pra adicionar outras buscas de data fixa nessa mesma lista.

## Configuracao (uma vez — ja feita)

Secrets em `Settings → Secrets and variables → Actions`:
- `TELEGRAM_TOKEN` — token do bot criado no @BotFather
- `TELEGRAM_CHAT_ID` — id do chat com o bot
- `SMTP_PASSWORD` — App Password do Gmail

## Limitacoes conhecidas

- `fast-flights` faz scraping nao-oficial do Google Flights: pode quebrar sem aviso.
  O agente manda um alerta no Telegram se ficar horas sem coletar nada.
- O preco coletado observado tem sido **igual em todos os horarios do dia** para esse
  trecho — pode ser um valor "generico" do Google Flights, nao necessariamente a
  tarifa exata de cada voo. **Sempre confirmar preco, horario e bagagem no site da
  Azul antes de comprar.**
- Horarios sugeridos para encaixar com o voo internacional (so informativo, a busca
  nao filtra por horario):
  - Ida: ~13:00 (pousa 14:05, ~7h50 de folga antes do voo intl das 21:55)
  - Volta: ~14:45 (sai ~4h50 depois do pouso do voo intl as 09:55)
- `cron` do GitHub Actions e "melhor esforco": pode atrasar 5–20 min.
