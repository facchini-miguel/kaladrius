# Deploy (Google Cloud, free tier)

[🇺🇸 English](../en/deploy.md) | 🇧🇷 Português | [🇪🇸 Español](../es/despliegue.md)

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
| Firewall | `medical-system-web-ipv6` (TCP 80/443 e UDP 443 para HTTP/3, de ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 só do IAP) | Grátis |
| Imagens | Artifact Registry `medical-system` (us-east1), limpeza automática (mantém 5 versões) | Free tier (0,5 GB) |
| Backups | `gs://medical-system-facchini-backups` (us-east1, privado, apaga após 30 dias) | Free tier (5 GB) |
| Contas de serviço | `medical-system-vm` (lê imagens, grava backups), `github-ci` (publica imagens) | Grátis |
| GitHub → Google | Workload Identity Federation (pool `github`), só o repositório e a branch `main` | Grátis |
| Alerta de orçamento | R$ 5 (avisos em 10%, 50% e 100%) | Grátis |

## Como o servidor funciona
- `deploy/servidor/instalar.sh` é o *startup script* da VM: instala Docker, cria 1 GB de swap, instala os agendamentos do systemd e sobe o sistema. Pode rodar de novo sem problema.
- `deploy/servidor/atualizar.sh` (a cada 5 min): baixa a imagem `latest`; se ela for diferente da última instalada com sucesso (`/opt/medical-system/imagem-instalada`), extrai os arquivos de `deploy/` de dentro da imagem, atualiza os agendamentos do systemd e reinicia os containers. Se algo falhar, tenta de novo na rodada seguinte. As migrações rodam na subida do app.
- `deploy/servidor/backup.sh` (diário): `pg_dump` enviado ao Cloud Storage e registrado no sistema; depois, apaga as tentativas de entrada recusadas com mais de 30 dias (`aplicar_retencao`). Se falhar, o systemd tenta de novo a cada 20 minutos (até 4 tentativas em 3 horas). Se o último backup registrado tiver mais de 26 horas, os superusuários veem um aviso no topo das telas.
- O compose de produção lê as variáveis `${...}` do `.env`, ligado ao lado dele (`/opt/medical-system/release/.env` → `../.env`). Só o app recebe o arquivo inteiro.
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

### Voltar para uma versão anterior
O normal é desfazer o commit (`git revert`) e enviar para a `main`: o CI publica uma imagem nova e a VM a instala em até 5 minutos. Numa emergência, dá para fixar uma imagem antiga na VM (cada versão tem a tag `X.Y.Z`, que nunca muda, e cada commit tem a tag com os 12 primeiros caracteres do SHA):

```bash
sudo systemctl stop medical-system-atualizar.timer   # senão a VM volta para a latest em 5 min
cd /opt/medical-system/release
sudo IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/medical-system/app:0.7.0 \
  docker compose -f docker-compose.prod.yml up -d app
# Depois de corrigir e publicar: sudo systemctl start medical-system-atualizar.timer
```
As migrações não são desfeitas: uma versão antiga só funciona se as migrações novas forem compatíveis com ela (só acrescentar tabelas e campos, por exemplo).

### Importar os dados do sistema antigo
Confirmado pelo titular em 27/10/2026, na clínica "Clínica Sorriso" (LGPD: os dados ficam nos EUA, e os backups também passam a ter dados reais). Veja [sistema-legado.md](sistema-legado.md).

```bash
# 1. Apagar os dados fictícios (clínicas "(teste)", seus dados e usuários de teste)
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py remover_dados_teste --confirmar'

# 2. Na sua máquina: o dump vai pelo túnel IAP direto para o comando, sem ficar gravado na VM
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py importar_legado - --clinica "Clínica Sorriso"' \
  < ~/medical-system-old_data/backup_20191106/facchini07_20191106.sql
```
Depois, vincule o administrador da clínica no admin do Django (Vínculos) e cadastre a equipe em Cadastros > Equipe. O superusuário já acessa a clínica pelo seletor de clínicas.

### Anonimizar os dados importados
Os dados da Clínica Sorriso servem só como dados de teste (decisão 047). Para anonimizá-los (irreversível; ver [sistema-legado.md](sistema-legado.md)):

```bash
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py anonimizar_clinica --clinica "Clínica Sorriso" --confirmar'
```
Rodar antes do backup diário seguinte à importação (06:00 UTC) evita que algum backup guarde os dados reais.

Para a clínica de teste ter agenda e rechamadas atuais (ver [sistema-legado.md](sistema-legado.md)):
```bash
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py simular_movimento --clinica "Clínica Sorriso" --confirmar'
```

### Restaurar um backup
```bash
# Na VM (substitui o banco atual!)
gcloud storage cp gs://medical-system-facchini-backups/<arquivo>.dump /tmp/restaurar.dump  # ou baixe pela sua máquina e copie com gcloud compute scp --tunnel-through-iap
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

### Testar a recuperação de um backup
Um backup só vale se voltar. O teste roda na sua máquina, num PostgreSQL temporário: baixa o backup, restaura (falha em qualquer erro), mostra quantos registros há em cada tabela e a última migração, e apaga tudo no fim. Não toca no servidor nem no banco de desenvolvimento.

```bash
deploy/testar_backup.sh                 # o backup mais recente
deploy/testar_backup.sh <arquivo>.dump  # um específico
```
Feito em 27/10/2026 com o backup de 26/10 (dados fictícios da época): restaurado sem erros em 9 segundos. O mesmo teste mostrou que o backup automático daquele dia tinha falhado (o servidor estava entre a 0.7.0 e a 0.8.0, sem o link do `.env`) e que o aviso na web não aparecia quando **nenhum** backup tinha sido registrado; desde a 0.17.1 os superusuários também veem esse caso (`DJANGO_BACKUP_MONITORADO`, ligado por padrão quando `DJANGO_DEBUG` está desligado).

## Cuidados
- **Dados reais de pacientes:** os dados ficam nos EUA (exigência do free tier). Antes de uso real, rever a LGPD (transferência internacional, art. 33) ou migrar para a região de São Paulo (paga).
- O disco **standard** é o gratuito; o console sugere "balanced", que é cobrado.
- Com dados reais no servidor, **não rode** `popular_dados_teste` em produção: ele cria usuários que compartilham a mesma senha (`DJANGO_SEED_PASSWORD`). Para apagá-los, `remover_dados_teste --confirmar`, que nunca toca em clínicas e usuários reais.
