---
sidebar_position: 9
title: Perguntas frequentes e problemas
---

# Perguntas frequentes e problemas

## É só para dentistas?

Não. Agenda, pacientes, rechamadas, orçamentos e financeiro servem para qualquer clínica. A clínica escolhe a sua **área** (Odontologia, Medicina ou outra área da saúde) nas Configurações da clínica: as partes de dentista, como o odontograma nos orçamentos, são um módulo que só aparece na Odontologia.

## Quanto custa?

O programa é gratuito e de código aberto (Apache 2.0). Você paga só por onde ele roda; no free tier do Google Cloud, pode ser zero.

## Uma instalação atende várias clínicas?

Não: uma instalação atende uma clínica, e ninguém escolhe clínica ao entrar. Para atender outra clínica, instale o sistema de novo (outro servidor, ou outro projeto do Compose no mesmo servidor).

## A página não abre ou o certificado falha

- Confira se o domínio aponta para o servidor: `dig +short AAAA clinica.exemplo.com.br` (ou `A`).
- Confira se as portas 80 e 443 estão abertas no firewall do servidor e no provedor de nuvem.
- Veja `kaladrius logs caddy`: o Let's Encrypt explica por que recusou.
- Num servidor só com IPv6, teste de uma rede com IPv6 (por exemplo, os dados móveis do celular).

## "Bad Request (400)"

Falta o domínio em `DJANGO_ALLOWED_HOSTS`. Acrescente e rode `kaladrius up -d`.

## "CSRF verification failed" ao entrar

Falta o domínio, com `https://`, em `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Alguém ficou bloqueado depois de errar a senha

O bloqueio acaba sozinho depois de 1 hora. Para liberar agora:

```bash
kaladrius exec app python manage.py axes_reset_username <usuário>
```

## Alguém esqueceu a senha

O administrador da clínica define uma nova em **Cadastros > Equipe > Definir nova senha**. Para o superusuário:

```bash
kaladrius exec app python manage.py changepassword <usuário>
```

## O servidor está lento ou ficou sem memória

Com 1 GB de RAM, mantenha o swap ligado. Todos veem memória, swap e disco em **Ajuda > Saúde do sistema** (instalação no Google Cloud). Com mais usuários, use 2 GB.

## Onde ficam os arquivos do sistema?

Não há: tudo está no banco, então o backup do banco é o backup do sistema.
