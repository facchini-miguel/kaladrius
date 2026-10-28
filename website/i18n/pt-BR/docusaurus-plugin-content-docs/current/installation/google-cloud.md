---
sidebar_position: 3
title: Free tier do Google Cloud
---

# Free tier do Google Cloud

A instalação de referência do Kaladrius roda no **free tier** do Google Cloud, sem custo mensal:

| Recurso | Escolha | Custo |
|---|---|---|
| VM | `e2-micro` em `us-east1`, `us-west1` ou `us-central1`, disco **standard** de 30 GB, Debian | Free tier |
| Endereço | Só **IPv6** externo (um IPv4 custa cerca de US$ 3,65/mês) | Grátis |
| Domínio | Subdomínio do DuckDNS com registro `AAAA` | Grátis |
| Imagens | Artifact Registry (até 0,5 GB) | Free tier |
| Backups | Bucket do Cloud Storage na mesma região (até 5 GB), apagados após 30 dias | Free tier |

Além do que tem o [servidor próprio](docker-compose.md), esta instalação traz:

- **Atualização automática:** a cada 5 minutos a VM procura uma imagem nova; se houver, instala e reinicia (`deploy/servidor/atualizar.sh`).
- **Backup diário** às 06:00 UTC no Cloud Storage, registrado no sistema, com novas tentativas (`deploy/servidor/backup.sh`).
- **Saúde do servidor** a cada 5 minutos (processador, memória, swap, disco, rede, containers), mostrada a todos em **Ajuda > Saúde do sistema** (`deploy/servidor/saude.sh`).
- **1 GB de swap**, necessário com 1 GB de RAM.
- Nenhuma senha ou chave do Google guardada: a VM e o CI usam tokens temporários.

## Como funciona

```
git push (main) ─> GitHub Actions: testes ─> build ─> Artifact Registry
                                                         │ a VM verifica a cada 5 min
                                                         ▼
Navegador ──IPv6/HTTPS──> VM e2-micro (sem IPv4 público)
                           ├─ caddy  (HTTPS automático)
                           ├─ app    (Django + Gunicorn, 127.0.0.1:8000)
                           ├─ db     (PostgreSQL 16)
                           └─ backup diário ─> bucket do Cloud Storage
Manutenção: SSH somente pelo túnel IAP do Google
```

## Passos

O [guia de deploy](https://github.com/facchini-miguel/kaladrius/blob/main/docs/pt-BR/deploy.md) do projeto registra cada recurso da instalação de referência. Em resumo:

1. **Projeto e orçamento.** Crie um projeto no Google Cloud e um alerta de orçamento (por exemplo, R$ 5) para perceber qualquer cobrança inesperada.
2. **Rede.** Uma VPC com sub-rede na região do free tier e **IPv6 externo**; reserve o IPv6 como fixo (grátis). Firewall: TCP 80/443 e UDP 443 de `::/0`, ICMPv6, e SSH (22) só da faixa do IAP `35.235.240.0/20`.
3. **Registro e bucket.** Um repositório no Artifact Registry para a imagem e um bucket privado no Cloud Storage com regra de exclusão em 30 dias.
4. **Contas de serviço.** Uma para a VM (lê imagens, grava backups) e uma para o GitHub Actions via Workload Identity Federation (publica imagens), limitada ao seu repositório e à branch `main`.
5. **VM.** `e2-micro`, disco standard, sem IPv4 externo, com `deploy/servidor/instalar.sh` como **startup script**. Ele instala o Docker, cria o swap, instala os agendamentos do systemd e sobe o sistema.
6. **Configuração.** Crie `/opt/medical-system/.env` (só root) com os valores de [Configuração](../configuration.md), incluindo `SITE_HOSTNAME` e `DUCKDNS_TOKEN`.
7. **Domínio.** Crie o subdomínio no DuckDNS e aponte para o IPv6:
   ```bash
   curl "https://www.duckdns.org/update?domains=<nome>&token=<token>&ipv6=<IPv6 da VM>"
   ```
8. **Primeiro administrador.** Pelo túnel IAP:
   ```bash
   gcloud compute ssh <vm> --zone=<zona> --tunnel-through-iap --command \
     'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec app python manage.py criar_admin'
   ```

## No dia a dia

```bash
# Entrar no servidor
gcloud compute ssh <vm> --zone=<zona> --tunnel-through-iap

# Na VM
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo /opt/medical-system/bin/atualizar.sh --forcar   # atualizar agora
sudo /opt/medical-system/bin/backup.sh               # backup agora
sudo /opt/medical-system/bin/saude.sh                # relatório da saúde do servidor
```

## Cuidados

- Escolha o disco **standard**: o console sugere o "balanced", que é cobrado.
- O free tier só existe em regiões dos EUA. Com dados reais de pacientes, isso é **transferência internacional de dados** pela LGPD (art. 33); avalie, ou use a região de São Paulo (paga).
- Só IPv6: o sistema só abre em redes com IPv6. Adicione um IPv4 à VM para atender qualquer rede.
