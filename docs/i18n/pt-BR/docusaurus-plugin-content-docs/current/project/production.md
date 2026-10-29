---
sidebar_position: 4
---

# Produção de referência

Ambiente publicado em **https://kaladrius.facchini.eti.br** (acesso somente por **IPv6**), também em https://kaladrius.duckdns.org. Endereço reserva: https://2600-1900-4020-f0b-0-0-0-0.sslip.io.

- **DNS:** `kaladrius.duckdns.org` (DuckDNS, gratuito) tem só registro AAAA para o IPv6 da VM. O token fica em `DUCKDNS_TOKEN` no `.env` do servidor e no `.env.producao` local. Para reapontar: `https://www.duckdns.org/update?domains=kaladrius&token=<token>&ipv6=<ipv6>` (com `ipv6` informado, o DuckDNS não preenche o IPv4). Atenção: ao **criar** um subdomínio pelo site, o DuckDNS preenche o IPv4 de quem criou (a sua casa); limpe com `&clear=true` e reaponte só o `ipv6`.
- **Documentação:** o site de `docs/` roda no mesmo servidor, em https://docs.facchini.eti.br, também em https://docs.kaladrius.duckdns.org (o DuckDNS responde qualquer `*.kaladrius.duckdns.org` com o mesmo IPv6, sem criar nada). O CI publica a imagem `docs` ao lado da `app`; ela só sobe com `COMPOSE_PROFILES=docs` e `DOCS_HOSTNAME` no `.env` do servidor. Ele é público e aberto aos buscadores desde a abertura do código (decisão 077). Para ver no seu computador: `docker compose --profile docs up --build docs` → http://localhost:3000.
- **Domínio do titular:** `kaladrius.facchini.eti.br` e `docs.facchini.eti.br` são CNAMEs no Registro.br para os nomes do DuckDNS, então acompanham o IPv6 sem nada a atualizar. O servidor aceita todos os nomes: `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` e `DOCS_HOSTNAME` são listas separadas por vírgula, e o Caddy tira um certificado por nome (decisão 084).
- **IPv6 fixo:** endereço reservado `kaladrius-ipv6` (`2600:1900:4020:f0b::`), gratuito; não muda ao reiniciar a VM.

## Arquitetura

```
git push (main) ─> GitHub Actions: testes ─> build ─> Artifact Registry (us-east1)
                                                          │ a VM verifica a cada 5 min
                                                          ▼
Navegador ──IPv6/HTTPS──> VM e2-micro "kaladrius" (us-east1-b, sem IPv4 público)
                           ├─ caddy  (HTTPS automático Let's Encrypt, rede do host)
                           ├─ app    (Django + Gunicorn, só em 127.0.0.1:8000)
                           ├─ db     (PostgreSQL 16, volume pgdata)
                           └─ backup diário 06:00 UTC ─> gs://kaladrius-backups
Manutenção: SSH somente pelo túnel IAP do Google
```

## Por que IPv6
O Google cobra o IPv4 público de VMs (US$ 0,005/hora, cerca de US$ 3,65/mês; o free tier cobre só 1 hora/mês). O IPv6 externo é gratuito. Consequência: o sistema só abre em redes com IPv6 (a maioria das redes móveis e muitas fixas no Brasil). Para atender qualquer rede, basta adicionar um IPv4 à VM (custo acima). Ver a [página de preços](https://cloud.google.com/vpc/network-pricing).

## Recursos (projeto `medical-system-facchini`, nome de exibição "Kaladrius")

| Recurso | Nome | Custo |
|---|---|---|
| VM | `kaladrius` (e2-micro, us-east1-b, disco standard 30 GB, Debian 13) | Free tier |
| Rede | VPC `medical-system`, sub-rede `medical-system-us-east1` (IPv4 interno + IPv6 externo, Private Google Access) | Grátis |
| IPv6 fixo | `kaladrius-ipv6` (`2600:1900:4020:f0b::`, reservado) | Grátis |
| Domínio | `kaladrius.facchini.eti.br` e `docs.facchini.eti.br` (domínio do titular no Registro.br, CNAMEs para o DuckDNS); `kaladrius.duckdns.org` (DuckDNS) | Grátis (DuckDNS); o titular paga o domínio dele |
| Firewall | `medical-system-web-ipv6` (TCP 80/443 e UDP 443 para HTTP/3, de ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 só do IAP) | Grátis |
| Imagens | Artifact Registry `kaladrius` (us-east1), limpeza automática (mantém 5 versões) | Free tier (0,5 GB) |
| Backups | `gs://kaladrius-backups` (us-east1, privado, apaga após 30 dias) | Free tier (5 GB) |
| Contas de serviço | `kaladrius-vm` (lê imagens, grava backups), `github-ci` (publica imagens) | Grátis |
| GitHub → Google | Workload Identity Federation (pool `github`), só o repositório e a branch `main` | Grátis |
| Alerta de orçamento | R$ 5 (avisos em 10%, 50% e 100%) | Grátis |

## Como o servidor funciona
- `deploy/servidor/instalar.sh` é o *startup script* da VM: instala Docker, cria 1 GB de swap, instala os agendamentos do systemd e sobe o sistema. Pode rodar de novo sem problema.
- `deploy/servidor/atualizar.sh` (a cada 5 min): baixa a imagem `latest`; se ela for diferente da última instalada com sucesso (`/opt/kaladrius/imagem-instalada`), extrai os arquivos de `deploy/` de dentro da imagem, atualiza os agendamentos do systemd e reinicia os containers. Se algo falhar, tenta de novo na rodada seguinte. As migrações rodam na subida do app.
- `deploy/servidor/backup.sh` (diário): `pg_dump` enviado ao Cloud Storage e registrado no sistema; depois, apaga as tentativas de entrada recusadas com mais de 30 dias (`aplicar_retencao`). Se falhar, o systemd tenta de novo a cada 20 minutos (até 4 tentativas em 3 horas). Se o último backup registrado tiver mais de 26 horas, os superusuários veem um aviso no topo das telas.
- `deploy/servidor/saude.sh --coletar` (a cada 5 min, desde a 0.22.0): lê processador, memória, swap, disco, rede e carga com comandos do Linux (`/proc`, `df`) e a memória e o processador de cada container (`docker stats`), e acrescenta uma linha em `/opt/kaladrius/saude/amostras.jsonl` (7 dias guardados, cerca de 1,5 MB). O app lê esse arquivo só para leitura e mostra **Administração > Saúde do sistema** aos superusuários, com um aviso no topo das telas se a coleta parar ou se a memória, o swap ou o disco chegarem ao nível crítico. O app não tem acesso ao Docker. Sem argumentos, `saude.sh` mostra um relatório no terminal.
- O compose de produção lê as variáveis `${...}` do `.env`, ligado ao lado dele (`/opt/kaladrius/release/.env` → `../.env`). Só o app recebe o arquivo inteiro.
- Configuração e senhas: `/opt/kaladrius/.env` (só root). Cópia local em `.env.producao`, ignorada pelo Git.
- Sem chaves guardadas: a VM e o CI usam tokens temporários do Google.

## Tarefas comuns

```bash
# Entrar no servidor (túnel IAP)
gcloud compute ssh kaladrius --zone=us-east1-b --tunnel-through-iap

# Na VM: estado, logs e comandos do Django
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <comando>

# Forçar atualização agora / backup agora
sudo /opt/kaladrius/bin/atualizar.sh --forcar
sudo /opt/kaladrius/bin/backup.sh

# Saúde do servidor: agora, últimas 24 horas, containers e agendamentos
sudo /opt/kaladrius/bin/saude.sh

# Listar backups (na sua máquina)
gcloud storage ls -l gs://kaladrius-backups/
```

### Voltar para uma versão anterior
O normal é desfazer o commit (`git revert`) e enviar para a `main`: o CI publica uma imagem nova e a VM a instala em até 5 minutos. Numa emergência, dá para fixar uma imagem antiga na VM (cada versão tem a tag `X.Y.Z`, que nunca muda, e cada commit tem a tag com os 12 primeiros caracteres do SHA):

```bash
sudo systemctl stop kaladrius-atualizar.timer   # senão a VM volta para a latest em 5 min
cd /opt/kaladrius/release
sudo IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app:0.7.0 \
  docker compose -f docker-compose.prod.yml up -d app
# Depois de corrigir e publicar: sudo systemctl start kaladrius-atualizar.timer
```
As migrações não são desfeitas: uma versão antiga só funciona se as migrações novas forem compatíveis com ela (só acrescentar tabelas e campos, por exemplo).

### Restaurar um backup
```bash
# Na VM (substitui o banco atual!)
gcloud storage cp gs://kaladrius-backups/<arquivo>.dump /tmp/restaurar.dump  # ou baixe pela sua máquina e copie com gcloud compute scp --tunnel-through-iap
cd /opt/kaladrius/release
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
