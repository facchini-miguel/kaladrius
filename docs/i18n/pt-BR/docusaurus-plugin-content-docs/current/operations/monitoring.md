---
sidebar_position: 3
title: Monitoramento
---

# Monitoramento

## Está no ar?

`GET /api/v1/versao` responde, sem login, com a versão instalada:

```bash
curl https://clinica.exemplo.com.br/api/v1/versao
# {"versao": "0.24.1"}
```

Use em qualquer monitor de disponibilidade (UptimeRobot, Healthchecks, Uptime Kuma…) para ser avisado quando o sistema parar de responder.

## Avisos por e-mail ou celular (instalação no Google Cloud)

O próprio servidor pode avisar você pelo [Healthchecks.io](https://healthchecks.io) (plano grátis: 20 verificações), que funciona com o servidor só IPv6:

1. Crie uma conta e uma verificação para cada linha abaixo (todas com o agendamento **Simple**). Escolha como quer ser avisado: e-mail, Telegram, Signal, notificação no celular…
2. Coloque os endereços delas no `.env` do servidor e pronto (os scripts leem na próxima execução). Qualquer linha pode ficar de fora.

| Variável no `.env` | Verificação | Período / tolerância | Avisa quando |
|---|---|---|---|
| `MONITOR_SISTEMA_URL` | Sistema no ar | 5 min / 10 min | O sistema, aberto pela internet pelo endereço dele (o primeiro nome de `SITE_HOSTNAME`), não responde, ou o banco dele não responde (`/api/v1/saude`) |
| `MONITOR_BACKUP_URL` | Backup diário | 1 dia / 2 h | O backup diário falha ou não roda |
| `MONITOR_DEMONSTRACAO_URL` | Reinício da demonstração (só no servidor da demonstração) | 1 dia / 2 horas | O reinício diário da demonstração (07:30 UTC) falha ou não roda |
| `MONITOR_RESTAURACAO_URL` | Restauração do backup | 7 dias / 1 dia | O teste semanal de restauração (domingos, 07:00 UTC: o backup mais novo restaurado num banco descartável) falha |
| `MONITOR_ATUALIZACAO_URL` | Atualização automática | 5 min / 15 min | As atualizações automáticas falham ou param de rodar |
| `MONITOR_RECURSOS_URL` | Disco e memória | 5 min / 15 min | Memória, swap ou disco chegam ao nível crítico |
| `MONITOR_CERTIFICADO_URL` | Certificado HTTPS | 1 dia / 2 h | Faltam menos de 14 dias para o certificado vencer (o Caddy renova uns 30 dias antes) |
| `MONITOR_DOCS_URL` | Documentação no ar | 5 min / 10 min | Este site de documentação, quando o servidor roda ele (`DOCS_HOSTNAME`), não responde |

Você é avisado quando um sinal informa falha ou **para de chegar**, o que também cobre o servidor inteiro desligado. Sem essas variáveis, nada é enviado.

## Avisos dentro do sistema

Os superusuários veem um aviso no topo das telas quando:

| Aviso | Quando | Configuração |
|---|---|---|
| **Backup** | Nenhum backup registrado nas últimas 26 horas, ou nenhum até hoje | `DJANGO_BACKUP_MONITORADO` |
| **Saúde do servidor** | A coleta parou, ou a memória, o swap ou o disco chegaram ao nível crítico | `DJANGO_SAUDE_MONITORADA` |

## Saúde do sistema (instalação no Google Cloud)

A cada 5 minutos, `deploy/servidor/saude.sh --coletar` lê processador, memória, swap, disco, rede, carga e a memória e o processador de cada container, e acrescenta uma linha em `/opt/kaladrius/saude/amostras.jsonl` (7 dias guardados, cerca de 1,5 MB). Todos veem em **Ajuda > Saúde do sistema**, com gráficos das últimas horas e dias; as tabelas do banco e o comando do servidor aparecem só para superusuários. O app só lê o arquivo; não tem acesso ao Docker.

No servidor, `sudo /opt/kaladrius/bin/saude.sh` mostra um relatório: agora, últimas 24 horas, containers e agendamentos.

## Logs

```bash
kaladrius logs -f app      # acessos, erros, migrações
kaladrius logs -f caddy    # certificados e acessos
kaladrius logs -f db       # banco de dados
```

## Auditoria

O que as pessoas fizeram dentro do sistema (quem criou, alterou, excluiu ou abriu cada registro, quando e de onde) fica em **Cadastros > Auditoria**, para o administrador da clínica. Veja [Configurações da clínica](../manual/clinica.md).
