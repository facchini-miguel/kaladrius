---
sidebar_position: 1
title: Atualização
---

# Atualização

O Kaladrius segue o [versionamento semântico](https://semver.org/lang/pt-BR/): `MAIOR.MENOR.CORREÇÃO`. Cada versão aparece, com o que mudou, em **Novidades** dentro do sistema e nas [releases do GitHub](https://github.com/facchini-miguel/kaladrius/releases). As migrações do banco rodam sozinhas quando o app sobe.

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
