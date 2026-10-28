---
sidebar_position: 1
title: Requisitos
---

# Requisitos

## Servidor

| | Mínimo | Confortável |
|---|---|---|
| Processador | 1 vCPU compartilhada (e2-micro do Google Cloud) | 2 vCPUs |
| Memória | 1 GB de RAM + 1 GB de swap | 2 GB de RAM |
| Disco | 10 GB | 30 GB (banco, imagens e backups locais) |
| Sistema operacional | Qualquer Linux que rode Docker (testado no Debian 13) | |
| Programas | Docker Engine com o plugin Compose, Git | |

A instalação de referência é uma **e2-micro** do Google Cloud (free tier) atendendo uma clínica pequena.

## Rede

- Um **domínio** apontando para o servidor: registro `A` (IPv4) e/ou `AAAA` (IPv6). Um subdomínio gratuito do [DuckDNS](https://www.duckdns.org) serve.
- Portas **80** e **443** abertas para a internet (443/UDP também, para HTTP/3). O Caddy, incluído, obtém e renova sozinho o certificado HTTPS do Let's Encrypt; a porta 80 é necessária para isso.
- Um servidor só com IPv6 só é acessível de redes com IPv6. A maioria das redes móveis e muitas conexões de casa e de escritório têm; para atender todo mundo, dê um endereço IPv4 ao servidor.

## Navegadores

Qualquer Chrome, Edge, Firefox ou Safari atual, no computador, tablet ou celular.

## Como instalar

| Opção | Para quem | Guia |
|---|---|---|
| **Servidor próprio** | Qualquer servidor Linux ou VPS com Docker | [Servidor próprio (Docker Compose)](docker-compose.md) |
| **Free tier do Google Cloud** | Sem custo de servidor; atualização automática, backup diário e monitoramento da saúde do servidor | [Google Cloud](google-cloud.md) |
| **Seu computador** | Avaliação e desenvolvimento | [Início rápido](../quick-start.md) |

## Antes de guardar dados reais de pacientes

Dados de saúde são dados pessoais sensíveis pela LGPD. Verifique onde fica o servidor (o free tier do Google Cloud fica nos Estados Unidos, o que é transferência internacional de dados), quem tem acesso a ele, e se os backups funcionam e estão guardados com segurança. Veja [Segurança e privacidade](../security.md).
