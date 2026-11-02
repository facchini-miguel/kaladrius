---
sidebar_position: 1
title: Atualização
---

# Atualização

O Kaladrius segue o [versionamento semântico](https://semver.org/lang/pt-BR/): `MAIOR.MENOR.CORREÇÃO`. Cada versão aparece, com o que mudou, em **Novidades** dentro do sistema e nas [releases do GitHub](https://github.com/facchini-miguel/kaladrius/releases). As migrações do banco rodam sozinhas quando o app sobe.

## Pacote Linux

Baixe o pacote da versão nova na [página de releases](https://github.com/facchini-miguel/kaladrius/releases) e instale por cima do instalado: `sudo apt install ./kaladrius_X.Y.Z-1_amd64.deb` ou `sudo dnf install ./kaladrius-X.Y.Z-1.x86_64.rpm`. Ele tem a mesma volta automática da instalação no Google Cloud (abaixo): uma versão que não responde em 5 minutos é desfeita e a anterior continua no ar; o `sudo kaladrius estado` mostra isso. Veja [Pacote Linux](../installation/linux-package.md#atualizações).

## Servidor próprio

```bash
cd /opt/kaladrius
sudo git pull                              # ou: sudo git checkout v0.25.0
sudo docker build -t kaladrius:latest .
kaladrius up -d
kaladrius logs -f app                      # espere o "Booting worker" e saia com Ctrl+C
```

Faça um [backup](backup-restore.md) antes de atualizar; é o único caminho de volta se algo der errado.

## Instalação no Google Cloud

Nada a fazer: a VM instala cada imagem nova publicada pelo CI em até 5 minutos. Para instalar agora:

```bash
sudo /opt/kaladrius/bin/atualizar.sh --forcar
```

**Volta automática:** depois de subir uma versão nova, a VM espera até 5 minutos o sistema responder a página de saúde (`/api/v1/saude`, com o banco). Se não responder, a VM põe de volta a versão da última atualização bem-sucedida (guardada como a imagem `app:anterior`) com o seu Compose e o seu Caddyfile, então uma imagem nova do Caddy ou do PostgreSQL também é desfeita, anota a nova como recusada, para não instalá-la de novo até sair uma versão mais nova, e o monitor "atualização automática" avisa da falha até lá. O `--forcar` tenta de novo a versão recusada. Uma migração que a versão nova já aplicou não é desfeita: se a versão anterior não funcionar com ela, restaure o backup.

## Voltar para uma versão anterior

As migrações não são desfeitas. Uma versão antiga só funciona se as migrações novas forem compatíveis com ela (por exemplo, só acrescentaram tabelas e campos). O caminho seguro é restaurar o backup feito antes da atualização.

No servidor próprio:

```bash
cd /opt/kaladrius
sudo git checkout v0.24.1
sudo docker build -t kaladrius:latest .
kaladrius up -d
```

No Google Cloud, pare antes a atualização automática, senão a VM volta para a imagem mais nova em 5 minutos:

```bash
sudo systemctl stop kaladrius-atualizar.timer
cd /opt/kaladrius/release
sudo IMAGEM_APP=<registro>/app:0.24.1 docker compose -f docker-compose.prod.yml up -d app
# depois de publicar a correção:
sudo systemctl start kaladrius-atualizar.timer
```

Cada versão tem uma tag de imagem `X.Y.Z` que nunca muda.
