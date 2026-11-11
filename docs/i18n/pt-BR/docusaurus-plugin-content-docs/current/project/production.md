---
sidebar_position: 4
---

# Produção de referência

Publicada em **https://kaladrius.facchini.eti.br** (IPv4 e IPv6), também em https://kaladrius.duckdns.org. O site de documentação fica em **https://kaladrius-docs.facchini.eti.br**, também em https://docs.kaladrius.duckdns.org. Desde 09/11/2026 os dois rodam na VPS do titular, gerenciados pelo [Dokploy](https://dokploy.com) (decisão 208); antes, numa VM do free tier do Google Cloud, só com IPv6.

- **DNS:** no Registro.br, `kaladrius` e `kaladrius-docs` têm um registro `A` (`179.66.139.4`) e um `AAAA` (`2a02:4780:95:91b7::1`). O Registro.br recusa um CNAME e um A/AAAA com o mesmo nome na mesma gravação: para trocar um CNAME por A/AAAA, grave primeiro a remoção e depois os registros novos. `kaladrius.duckdns.org` aponta para os mesmos dois endereços (`https://www.duckdns.org/update?domains=kaladrius&token=<token>&ip=<ipv4>&ipv6=<ipv6>`; o token é o `DUCKDNS_TOKEN` do `.env` do servidor), e o DuckDNS responde qualquer `*.kaladrius.duckdns.org` com eles.
- **Nomes:** o servidor aceita todos os nomes. `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` e `DOCS_HOSTNAME` são listas separadas por vírgula, e o Traefik tira um certificado por nome, cada um com o seu roteador, então um nome com o DNS ainda não pronto não segura os outros.
- **Documentação:** pública e aberta aos buscadores desde a abertura do código (decisões 077 e 207). Para ver no seu computador: `docker compose --profile docs up --build docs` → http://localhost:3000.

## Arquitetura

```
git push (main) ─> GitHub Actions: testes, build das docs ─> imagem no ghcr.io
                                                               │ o servidor verifica a cada 5 min
                                                               ▼
Navegador ──IPv4/IPv6, HTTPS──> VPS (Ubuntu 24.04, Hostinger, Boston, EUA)
                                 ├─ traefik  (proxy do Dokploy: HTTPS Let's Encrypt, portas 80/443)
                                 └─ Compose "kaladrius" do Dokploy
                                     ├─ app   (Django + Gunicorn, imagem do ghcr.io)
                                     ├─ db    (PostgreSQL 16, volume pgdata)
                                     └─ docs  (gerado do docs/ da main a cada deploy)
Backup diário 06:00 UTC ─> /var/backups/kaladrius (30 dias)
Manutenção: SSH só com chave (sem senha, sem root); painel do Dokploy só por túnel SSH
```

## Servidor

| Item | Valor |
|---|---|
| Máquina | VPS na Hostinger (Boston, EUA): 8 vCPUs, 32 GB de RAM, 400 GB de disco, Ubuntu 24.04 |
| Acesso | `ssh facchini@179.66.139.4`, só com chave; `sudo` para administrar |
| Firewall | ufw: só 22, 80 e 443. O Docker publica portas por fora do ufw, então o painel do Dokploy (3000) fica fechado para a internet por uma regra na cadeia `DOCKER-USER` (`bloquear-painel-dokploy.service`) |
| Dokploy | projeto **Kaladrius**, Compose **kaladrius** (arquivo Compose guardado no próprio Dokploy). O painel: `ssh -L 3000:localhost:3000 facchini@179.66.139.4` e depois http://localhost:3000 |
| Configurações | o ambiente do Compose no Dokploy (gravado como `.env` ao lado do arquivo Compose). Veio do `.env` do Google Cloud, sem o nome `sslip.io` |

O arquivo Compose segue o `deploy/docker-compose.prod.yml`, com o Traefik no lugar do Caddy: os labels dão HTTPS para cada nome, redirecionam HTTP para HTTPS, comprimem as respostas, tiram o cabeçalho `Server` e limitam o corpo de uma requisição a 11 MB (o maior envio legítimo é um anexo de 10 MB do prontuário, como o `request_body` do Caddyfile). O app confia no endereço do cliente que o Traefik põe por último no `X-Forwarded-For` (`DJANGO_REVERSE_PROXY=1`).

**A documentação não depende do app** (decisão 209): as rotas dela usam middlewares do Traefik próprios (`kaladrius-docs-comprime`, `kaladrius-docs-sem-server`, `kaladrius-docs-https`), declarados no serviço `docs`. Quando usavam os declarados no `app`, o Traefik derrubava as rotas da documentação sempre que o app parava (o reinício noturno, toda atualização). O `update-dokploy.sh`, como o `reset_demo.sh`, marca a parada como manutenção, para o `health.sh` não acusá-la.

## Como o servidor funciona

Os scripts de `deploy/server/` rodam como estão, de `/opt/kaladrius/bin`, com as units do systemd do repositório. `/opt/kaladrius` liga os scripts ao Compose do Dokploy:

- `release/docker-compose.prod.yml` e `release/.env` são links para o arquivo Compose e o `.env` do Dokploy. O `.env` dá o nome do projeto Compose (`COMPOSE_PROJECT_NAME`), então `docker compose -f /opt/kaladrius/release/docker-compose.prod.yml` chega aos containers que o Dokploy subiu.
- `/opt/kaladrius/.env` é uma cópia sem aspas, que o `sync-env.py` refaz antes de cada unit `kaladrius-*` (drop-in `/etc/systemd/system/kaladrius-.service.d/env.conf`). O Dokploy grava `CHAVE="valor"`, que o Docker Compose entende, mas o `env_value` do `common.sh` lê a linha como está: com aspas, `DJANGO_DEMO="1"` nunca seria igual a `1` e os endereços dos monitores ficariam inválidos. Mude as configurações no Dokploy, nunca nessa cópia.
- `release/linux-package` põe os scripts no modo de instalação em servidor próprio (decisão 140): backups e teste de restauração numa pasta local, e os sites testados pelo próprio servidor. A imagem e as atualizações ficam com o Dokploy.

| Timer | O que faz |
|---|---|
| `kaladrius-update.timer` (a cada 5 min) | `update-dokploy.sh`: baixa `ghcr.io/facchini-miguel/kaladrius:latest`; se for diferente do app que está rodando, pede ao Dokploy um deploy do Compose (app novo, docs geradas de novo da main), espera o `/api/v1/health` e avisa o `MONITOR_UPDATE_URL`. As migrações rodam quando o app sobe. Aqui não há a volta automática da decisão 135: veja abaixo |
| `kaladrius-backup.timer` (06:00 UTC) | `backup.sh`: `pg_dump` em `/var/backups/kaladrius`, guardando `KALADRIUS_BACKUP_DAYS` (30) dias; registra no sistema e aplica a retenção de 30 dias dos logins recusados |
| `kaladrius-restore-test.timer` (domingos 07:00 UTC) | `test_restore.sh`: restaura o backup mais novo num banco descartável e confere |
| `kaladrius-demo-reset.timer` (07:30 UTC) | `reset_demo.sh`: o reinício diário da demonstração (abaixo) |
| `kaladrius-health.timer` (a cada 5 min) | `health.sh --collect`: as amostras de **Administração > Saúde do sistema** (`/opt/kaladrius/health`) e os monitores dos sites, certificados e recursos |
| `backup-dokploy.timer` (05:30 UTC) | o banco do próprio Dokploy e `/etc/dokploy` em `/var/backups/dokploy` (14 dias) |

Os monitores externos (Healthchecks.io, decisão 078) são os `MONITOR_*_URL` do `.env`, os mesmos do Google Cloud.

**Por enquanto os backups ficam no disco da VPS.** Ainda falta escolher onde guardar uma cópia fora dela. Os 18 backups do bucket do Google Cloud (26/10 a 09/11) estão em `/var/backups/kaladrius/google`.

## Tarefas comuns

```bash
# Entrar no servidor
ssh facchini@179.66.139.4

# No servidor: estado, logs e comandos do Django
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <comando>

# Atualizar agora / backup agora
sudo systemctl start kaladrius-update.service
sudo systemctl start kaladrius-backup.service

# Saúde do servidor: agora, últimas 24 horas, containers e timers
sudo /opt/kaladrius/bin/health.sh

# Listar backups
sudo ls -l /var/backups/kaladrius
```

### Voltar para uma versão anterior
O caminho normal é reverter o commit (`git revert`) num branch e levá-lo à `main` por pull request (a `main` não recebe outra coisa, decisão 141; o administrador pode fazer push direto, passando por cima do ruleset): o CI publica uma imagem nova e o servidor a instala em até 5 minutos depois do merge. Numa emergência, dá para fixar uma imagem antiga (cada versão tem no ghcr.io uma tag `X.Y.Z` que nunca muda, e cada commit uma tag com os 12 primeiros caracteres do SHA): pare o `kaladrius-update.timer`, troque o `image:` do app no arquivo Compose do Dokploy por `ghcr.io/facchini-miguel/kaladrius:<tag>` e faça o deploy. Depois de corrigir e publicar, volte para `latest` e ligue o timer de novo.

As migrações não são desfeitas: uma versão antiga só funciona se as migrações novas forem compatíveis com ela (tabelas novas, ou campos que podem ficar vazios ou têm `db_default`, por exemplo; o relatório de migrações de cada pull request aponta o resto, decisão 139).

### Restaurar um backup
```bash
# No servidor (substitui o banco atual!)
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /var/backups/kaladrius/<arquivo>.dump
```

### Testar a recuperação de um backup
Um backup só vale se voltar. O servidor testa o mais novo todo domingo (`kaladrius-restore-test.timer`), num banco descartável que nunca toca no de verdade; para testar agora, `sudo systemctl start kaladrius-restore-test.service`. (O `deploy/test_backup.sh` testa na sua máquina os backups de um bucket do Google Cloud, o jeito de uma instalação no Google Cloud.)

Feito em 09/11/2026, na mudança para a VPS: o dump da produção foi restaurado sem erros (9 usuários, 1.093 pacientes, 19.446 agendamentos), e o teste de restauração passou com o primeiro backup da VPS.

## Contas públicas de demonstração
A demonstração publica uma conta de cada perfil no site do titular: `demo.recepcao`, `demo.profissional`, `demo.financeiro` e `demo.admin` (decisões 085 e 089). Por serem de demonstração, elas nunca trocam a senha, enviam anexos, mudam a equipe ou as configurações da clínica, nem veem os IPs na auditoria. Para criá-las, ou para reiniciar as senhas:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py demo_accounts \
  --clinic "Clínica Sorriso" --practitioner "Dra. Demonstração" --create-practitioner \
  --front-desk-password <senha publicada> --practitioner-password <senha publicada> \
  --finance-password <senha publicada> --admin-password <senha publicada>
```

Nunca use ali a senha de `DJANGO_SEED_PASSWORD`: os usuários de teste, inclusive o administrador de teste, usam essa senha.

### Reinício diário (decisão 086)
Todo dia às 07:30 UTC (04:30 em Brasília, depois do backup) o servidor restaura uma **base** salva da demonstração, desfazendo o que os visitantes mudaram, e avança todas as datas pelas semanas inteiras desde que a base foi salva, para a agenda sempre parecer atual e cada consulta ficar no mesmo dia da semana (datas de nascimento não mudam). A lista de backups é mantida. Só roda com `DJANGO_DEMO=1` no `.env` do servidor (no Dokploy). A base é `/opt/kaladrius/demo/base.dump`, trazida do Google Cloud (salva em 07/11/2026) e salva de novo na VPS em 11/11/2026, logo depois de um reinício, para o reinício não reaplicar mais as migrações desde a 0.62 (decisão 209). A data dela (`base-date`) continua 07/11/2026, a data dos agendamentos nela: uma base salva logo depois de um reinício ainda tem as datas da base anterior, já que o reinício só as move depois de uma semana inteira. Para salvar de novo:

```bash
sudo /opt/kaladrius/bin/reset_demo.sh --save-base
```

As contas dos **administradores do sistema** (superusuários) são mantidas no reinício (decisão 118): senha, e-mail, idioma, verificação em duas etapas e códigos de recuperação ficam como estavam. O restante das configurações **do titular** (as da clínica, por exemplo) volta para a base: depois de mudar uma que deve ficar, salve a base de novo (`--save-base`). Para reiniciar na hora: `sudo systemctl start kaladrius-demo-reset.service`.

## Cuidados
- **Dados reais de pacientes:** o servidor fica nos Estados Unidos. Antes de uso real, rever a LGPD (transferência internacional, art. 33) ou mudar para um servidor no Brasil.
- Com dados reais no servidor, **não rode** `seed_sample_data` em produção: ele cria usuários que compartilham a mesma senha (`DJANGO_SEED_PASSWORD`). Para apagá-los, `remove_sample_data --confirm`, que nunca toca em clínicas e usuários reais.
- A chave de API do Dokploy (`~/.dokploy-api-key` do `facchini` no servidor) é o que permite ao `update-dokploy.sh` fazer o deploy: quando ela vencer ou for revogada, as atualizações param e o `MONITOR_UPDATE_URL` avisa.
