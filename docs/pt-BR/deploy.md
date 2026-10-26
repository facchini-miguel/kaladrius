# Deploy (Google Cloud, free tier)

[🇺🇸 English](../en/deploy.md) | 🇧🇷 Português

Ambiente publicado em **https://medical-system.duckdns.org** (acesso somente por **IPv6**). Endereço reserva: https://2600-1900-4020-f0b-0-0-0-0.sslip.io.

- **DNS:** `medical-system.duckdns.org` (DuckDNS, gratuito) tem só registro AAAA para o IPv6 da VM. O token fica em `DUCKDNS_TOKEN` no `.env` do servidor e no `.env.producao` local. Para reapontar: `https://www.duckdns.org/update?domains=medical-system&token=<token>&ipv6=<ipv6>` (com `ipv6` informado, o DuckDNS não preenche o IPv4).
- **IPv6 fixo:** endereço reservado `medical-system-ipv6` (`2600:1900:4020:f0b::`), gratuito; não muda ao reiniciar a VM.

## Arquitetura

```
git push (main) ─> GitHub Actions: testes ─> build ─> Artifact Registry (us-east1)
                                                          │ a VM verifica a cada 5 min
                                                          ▼
Navegador ──IPv6/HTTPS──> VM e2-micro "medical-system" (us-east1-b, sem IPv4 público)
                           ├─ caddy  (HTTPS automático Let's Encrypt, rede do host)
                           ├─ app    (Django + Gunicorn, só em 127.0.0.1:8000)
                           ├─ db     (PostgreSQL 16, volume pgdata)
                           └─ backup diário 06:00 UTC ─> gs://medical-system-facchini-backups
Manutenção: SSH somente pelo túnel IAP do Google
```

## Por que IPv6
O Google cobra o IPv4 público de VMs (US$ 0,005/hora, cerca de US$ 3,65/mês; o free tier cobre só 1 hora/mês). O IPv6 externo é gratuito. Consequência: o sistema só abre em redes com IPv6 (a maioria das redes móveis e muitas fixas no Brasil). Para atender qualquer rede, basta adicionar um IPv4 à VM (custo acima). Ver a [página de preços](https://cloud.google.com/vpc/network-pricing).

## Recursos (projeto `medical-system-facchini`)

| Recurso | Nome | Custo |
|---|---|---|
| VM | `medical-system` (e2-micro, us-east1-b, disco standard 30 GB, Debian 13) | Free tier |
| Rede | VPC `medical-system`, sub-rede `medical-system-us-east1` (IPv4 interno + IPv6 externo, Private Google Access) | Grátis |
| IPv6 fixo | `medical-system-ipv6` (`2600:1900:4020:f0b::`, reservado) | Grátis |
| Domínio | `medical-system.duckdns.org` (DuckDNS) | Grátis |
| Firewall | `medical-system-web-ipv6` (80/443 de ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 só do IAP) | Grátis |
| Imagens | Artifact Registry `medical-system` (us-east1), limpeza automática (mantém 5 versões) | Free tier (0,5 GB) |
| Backups | `gs://medical-system-facchini-backups` (us-east1, privado, apaga após 30 dias) | Free tier (5 GB) |
| Contas de serviço | `medical-system-vm` (lê imagens, grava backups), `github-ci` (publica imagens) | Grátis |
| GitHub → Google | Workload Identity Federation (pool `github`), só o repositório e a branch `main` | Grátis |
| Alerta de orçamento | R$ 5 (avisos em 10%, 50% e 100%) | Grátis |

## Como o servidor funciona
- `deploy/servidor/instalar.sh` é o *startup script* da VM: instala Docker, cria 1 GB de swap, instala os agendamentos do systemd e sobe o sistema. Pode rodar de novo sem problema.
- `deploy/servidor/atualizar.sh` (a cada 5 min): baixa a imagem `latest`; se mudou, extrai os arquivos de `deploy/` de dentro da imagem e reinicia os containers. As migrações rodam na subida do app.
- `deploy/servidor/backup.sh` (diário): `pg_dump` enviado ao Cloud Storage.
- Configuração e senhas: `/opt/medical-system/.env` (só root). Cópia local em `.env.producao`, ignorada pelo Git.
- Sem chaves guardadas: a VM e o CI usam tokens temporários do Google.

## Tarefas comuns

```bash
# Entrar no servidor (túnel IAP)
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap

# Na VM: estado, logs e comandos do Django
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <comando>

# Forçar atualização agora / backup agora
sudo /opt/medical-system/bin/atualizar.sh --forcar
sudo /opt/medical-system/bin/backup.sh

# Listar backups (na sua máquina)
gcloud storage ls -l gs://medical-system-facchini-backups/
```

### Restaurar um backup
```bash
# Na VM (substitui o banco atual!)
gcloud storage cp gs://medical-system-facchini-backups/<arquivo>.dump /tmp/restaurar.dump  # ou baixe pela sua máquina e copie com gcloud compute scp --tunnel-through-iap
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

## Cuidados
- **Dados reais de pacientes:** os dados ficam nos EUA (exigência do free tier). Antes de uso real, rever a LGPD (transferência internacional, art. 33) ou migrar para a região de São Paulo (paga).
- O disco **standard** é o gratuito; o console sugere "balanced", que é cobrado.
- Os dados atuais do servidor são **fictícios** (`popular_dados_teste --forcar`).
