---
sidebar_position: 2
title: Pacote Linux (.deb, .rpm e Arch Linux)
---

# Pacote Linux (.deb, .rpm e Arch Linux)

O jeito mais simples de instalar o Kaladrius num servidor da clínica ou numa VPS: um pacote da distribuição, que instala o Docker sozinho e faz algumas perguntas em telas de texto. Nenhum arquivo para editar à mão.

## Sistemas aceitos

| Sistema | Pacote | Docker |
|---|---|---|
| Debian 13 ou mais novo, Ubuntu 24.04 ou mais novo | `.deb` | da própria distribuição, instalado junto com o pacote |
| Fedora, openSUSE Tumbleweed | `.rpm` | da própria distribuição, instalado junto com o pacote |
| Arch Linux, CachyOS | `.pkg.tar.zst` (baixado; fora do repositório) | da própria distribuição, instalado junto com o pacote. Distribuições *rolling release*: boas para experimentar o Kaladrius; para o servidor de uma clínica, prefira um dos sistemas acima |
| Rocky Linux, AlmaLinux, Red Hat Enterprise Linux | `.rpm` | acrescente antes o [repositório do Docker](https://docs.docker.com/engine/install/rhel/) (abaixo) |
| Debian 12, Ubuntu 22.04 | `.deb` | o Docker Compose deles é antigo demais: instale antes os [pacotes do próprio Docker](https://docs.docker.com/engine/install/debian/) |

Só processadores Intel e AMD de 64 bits (`amd64` / `x86_64`). O servidor precisa das portas **80** e **443** livres: o Kaladrius traz o próprio servidor web, o Caddy, com HTTPS. Com um firewall ligado (firewalld no Fedora, Rocky, AlmaLinux e openSUSE; ufw no Ubuntu), o `kaladrius configurar` abre as duas. Memória e disco: veja [Requisitos](requirements.md).

No Rocky Linux, AlmaLinux e Red Hat Enterprise Linux:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
```

## Instalar

### Pelo repositório de pacotes

Com o repositório de pacotes [packages.facchini.eti.br](https://packages.facchini.eti.br) adicionado, as versões novas do Kaladrius chegam com as atualizações do próprio sistema. No Debian e no Ubuntu:

```bash
sudo apt install -y curl ca-certificates
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSLo /etc/apt/keyrings/facchini.asc https://packages.facchini.eti.br/chave.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/facchini.asc] https://packages.facchini.eti.br/deb stable main" | sudo tee /etc/apt/sources.list.d/facchini.list
sudo apt update
sudo apt install kaladrius
```

No Fedora, Rocky Linux, AlmaLinux e Red Hat Enterprise Linux:

```bash
sudo curl -fsSLo /etc/yum.repos.d/facchini.repo https://packages.facchini.eti.br/rpm/facchini.repo
sudo dnf install kaladrius
```

No openSUSE:

```bash
sudo zypper addrepo https://packages.facchini.eti.br/rpm/facchini.repo
sudo zypper install kaladrius
```

O repositório e os pacotes `.rpm` dele são assinados. Antes de confiar na chave, o `dnf` e o `zypper` mostram a impressão digital dela, que precisa ser `9D3A 0438 FF6C 00F9 1CA1 A0AB A5C3 35B2 EB36 7ABA`.

No Debian e no Ubuntu as perguntas aparecem na hora, no idioma do servidor (português, espanhol ou inglês). Com `dnf` e `zypper`, rode-as você mesmo em seguida:

```bash
sudo kaladrius configurar
```

### Por um pacote baixado

No Arch Linux e no CachyOS, que o repositório não atende, ou para escolher a versão à mão:

1. Baixe o pacote da versão mais nova na [página de releases](https://github.com/facchini-miguel/kaladrius/releases/latest), com o arquivo `SHA256SUMS` para conferi-lo. Por exemplo, para a versão 0.54.0:

   ```bash
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/kaladrius_0.54.0-1_amd64.deb
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/SHA256SUMS
   sha256sum --ignore-missing -c SHA256SUMS    # deve dizer: OK (ou SUCESSO)
   ```

   No Fedora, openSUSE, Rocky e AlmaLinux o arquivo é `kaladrius-0.54.0-1.x86_64.rpm`; no Arch Linux e no CachyOS, `kaladrius-0.54.0-1-x86_64.pkg.tar.zst`.

2. Instale:

   ```bash
   sudo apt install ./kaladrius_0.54.0-1_amd64.deb       # Debian e Ubuntu
   sudo dnf install ./kaladrius-0.54.0-1.x86_64.rpm      # Fedora, Rocky, AlmaLinux
   sudo zypper install ./kaladrius-0.54.0-1.x86_64.rpm   # openSUSE
   sudo pacman -Syu && sudo pacman -U ./kaladrius-0.54.0-1-x86_64.pkg.tar.zst   # Arch Linux, CachyOS
   ```

   No Debian e no Ubuntu as perguntas aparecem na hora; com `dnf`, `zypper` e `pacman`, rode `sudo kaladrius configurar` em seguida.

Um pacote baixado não é assinado: o `dnf` e o `zypper` avisam isso ("skipped OpenPGP checks", "unsigned rpm"). Quem prova que o arquivo é o publicado é a conferência do `SHA256SUMS` acima.

## As perguntas

1. **Como a clínica vai acessar o Kaladrius**
   - **Só na rede interna da clínica:** não precisa de domínio. O instalador sugere o endereço IP deste servidor na rede (por exemplo `192.168.0.10`). Esse endereço não pode mudar: reserve-o para o servidor no roteador (*reserva de DHCP*), ou dê ao servidor um IP fixo.
   - **Pela internet, com domínio:** o domínio (por exemplo `clinica.exemplo.com.br`) já deve apontar para este servidor, com as portas 80 e 443 abertas na internet, para o certificado gratuito do Let's Encrypt. O instalador confere o domínio no DNS e não segue sem ele.
2. **O administrador:** o nome de usuário (`admin`, se você não mudar), um e-mail opcional e a senha, digitada duas vezes. Ela precisa de pelo menos 10 caracteres, não pode ter só números nem ser uma senha comum; quando o sistema a recusa, a tela diz o motivo e pede de novo. A senha não fica guardada em nenhum arquivo.

Depois o sistema é baixado e iniciado (alguns minutos na primeira vez), e a última tela mostra o endereço para abrir no navegador. Entre com o administrador e siga os [Primeiros passos](../first-steps.md): os dados da clínica são preenchidos ali.

Para mudar o endereço depois (um IP novo, ou passar da rede interna para um domínio), rode `sudo kaladrius configurar` de novo: senhas, chaves e dados ficam.

## Rede interna: o certificado

Na rede interna o certificado HTTPS é emitido pela própria instalação, então, até os computadores da clínica confiarem nele, o navegador mostra um aviso de segurança. Exporte o certificado uma vez:

```bash
sudo kaladrius certificado        # salva kaladrius-certificado.crt na pasta atual
```

Copie esse arquivo (num pen drive, por exemplo) para cada computador da clínica e instale-o:

| Em | Como |
|---|---|
| Windows | dois cliques no arquivo > **Instalar Certificado** > **Máquina Local** > **Colocar todos os certificados no repositório a seguir** > **Autoridades de Certificação Raiz Confiáveis** |
| macOS | dois cliques > **Acesso às Chaves**, chaveiro **Sistema**; depois abra o certificado, **Confiar** > **Confiar Sempre** |
| Linux | `sudo cp kaladrius-certificado.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates` |
| Firefox (qualquer sistema) | **Configurações** > **Privacidade e Segurança** > **Certificados** > **Ver certificados** > **Autoridades** > **Importar** |
| Android, iPhone | envie o arquivo para o aparelho e abra-o; no iPhone, depois ative em **Ajustes** > **Geral** > **Sobre** > **Ajustes de Confiança de Certificados** |

O certificado é só desta instalação. Ele continua o mesmo quando o endereço do servidor muda, então é instalado uma vez em cada computador.

## Instalação por um técnico (sem perguntas)

Com todas as opções e a senha do administrador em `KALADRIUS_SENHA_ADMIN`, o `configurar` não pergunta nada. O `read -rs` deixa a senha fora do histórico do terminal:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y ./kaladrius_0.54.0-1_amd64.deb
read -rs KALADRIUS_SENHA_ADMIN && export KALADRIUS_SENHA_ADMIN
sudo --preserve-env=KALADRIUS_SENHA_ADMIN kaladrius configurar \
  --acesso rede-interna --endereco 192.168.0.10 --usuario admin --email ti@clinica.exemplo
```

`--acesso` é `rede-interna` ou `internet`; com `internet`, o `--endereco` é o domínio. Num erro (um endereço inválido, uma senha recusada) ele para com o motivo e um código de saída diferente de zero.

## Comandos do dia a dia

| Comando | O que faz |
|---|---|
| `sudo kaladrius estado` | endereço, versão e situação dos serviços |
| `sudo kaladrius saude` | processador, memória, disco, os últimos backups e as tarefas agendadas |
| `sudo kaladrius backup` | faz um backup agora |
| `sudo kaladrius testar-restauracao` | restaura o backup mais novo num banco descartável e confere |
| `sudo kaladrius certificado [ARQUIVO]` | o certificado para os computadores da rede interna |
| `sudo kaladrius senha [USUARIO]` | troca a senha de um usuário (do administrador, se nenhum for dado) |
| `sudo kaladrius logs [app\|db\|caddy]` | os registros dos serviços (Ctrl+C para sair) |
| `sudo kaladrius reiniciar` | reinicia os serviços, aplicando as mudanças de `/opt/kaladrius/.env` |
| `sudo kaladrius parar` / `iniciar` | para ou inicia o sistema; os dados ficam |
| `kaladrius ajuda` | a lista de comandos |

## Backups

Todo dia às 06:00 UTC (03:00 em Brasília) o banco é salvo em `/var/backups/kaladrius`, e os últimos 14 dias são guardados. Todo domingo o backup mais novo é restaurado num banco descartável e conferido. Cada backup é registrado no sistema: os superusuários veem um aviso no alto de todas as páginas quando o último tem mais de 26 horas.

:::warning
Um backup no mesmo disco não sobrevive à perda do disco. Copie `/var/backups/kaladrius` todo dia para outro computador, um disco externo ou um armazenamento na nuvem (por exemplo com o `rclone`). Os arquivos têm dados de pacientes: guarde-os em lugar privado e criptografado.
:::

A pasta e o número de dias são `KALADRIUS_BACKUP_PASTA` e `KALADRIUS_BACKUP_DIAS` em `/opt/kaladrius/.env`. Para restaurar um backup, veja [Backup e restauração](../operations/backup-restore.md#pacote-linux).

## Atualizações

Faça um backup antes (`sudo kaladrius backup`) e então:

- **Instalado pelo repositório:** `sudo apt update && sudo apt upgrade`, `sudo dnf upgrade` ou `sudo zypper update`, junto com o resto do sistema. Uma versão nova chega ao repositório em até uma hora depois de lançada.
- **Por um pacote baixado:** baixe o pacote da versão nova e instale do mesmo jeito (`sudo apt install ./kaladrius_….deb`, `sudo dnf install ./kaladrius-….rpm` ou `sudo pacman -U ./kaladrius-….pkg.tar.zst`).

O sistema reinicia na versão nova; as migrações do banco rodam sozinhas.

**Volta automática:** se a versão nova não responder em 5 minutos, a anterior volta sozinha, com o arquivo do Compose e o Caddyfile dela, e continua no ar, e o `sudo kaladrius estado` mostra o aviso. `sudo kaladrius reiniciar`, `parar` e `iniciar` mantêm a versão anterior; instalar o pacote de novo (`sudo apt install --reinstall kaladrius`, `sudo dnf reinstall kaladrius`, `sudo zypper install -f kaladrius` ou o arquivo baixado) tenta a nova outra vez.

## E-mail e monitoramento (opcionais)

O arquivo `/opt/kaladrius/.env` tem as configurações de e-mail para a recuperação de senha (`DJANGO_EMAIL_*`, veja [Configuração](../configuration.md)) e aceita os endereços do monitor externo (`MONITOR_*_URL`, veja [Monitoramento](../operations/monitoring.md)). Depois de editá-lo: `sudo kaladrius reiniciar`.

## Desinstalar

```bash
sudo apt remove kaladrius                      # Debian, Ubuntu
sudo dnf remove --noautoremove kaladrius       # Fedora, Rocky, AlmaLinux
sudo zypper remove kaladrius                   # openSUSE
sudo pacman -R kaladrius                       # Arch Linux, CachyOS
```

O sistema para, e **os dados ficam**: o banco (volume Docker `kaladrius_pgdata`), os backups em `/var/backups/kaladrius` e o `/opt/kaladrius/.env`, com a senha do banco. Instalar o pacote de novo traz o sistema de volta com eles. Sem o `--noautoremove`, o dnf também remove o Docker quando ele veio com o pacote; os dados ficam, mas aí instalar de novo precisa da internet para baixar o Docker. Apagá-los é irreversível e é feito à mão; os comandos aparecem quando o pacote é removido.

Para remover também o repositório de pacotes: `sudo rm /etc/apt/sources.list.d/facchini.list /etc/apt/keyrings/facchini.asc` (Debian, Ubuntu), `sudo rm /etc/yum.repos.d/facchini.repo` (Fedora, Rocky, AlmaLinux) ou `sudo zypper removerepo facchini` (openSUSE).

## Onde fica cada coisa

| Caminho | O quê |
|---|---|
| `/opt/kaladrius/.env` | as configurações e chaves da instalação (só o root lê) |
| `/opt/kaladrius/release/` | o arquivo do Compose e o Caddyfile da versão instalada |
| `/opt/kaladrius/bin/` | o comando `kaladrius` e os scripts do servidor |
| `/var/backups/kaladrius/` | os backups diários |
| `kaladrius-*.timer` (systemd) | backup, amostras de saúde a cada 5 minutos, teste semanal de restauração |
