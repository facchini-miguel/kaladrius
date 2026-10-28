---
sidebar_position: 7
title: Segurança e privacidade
---

# Segurança e privacidade

O Kaladrius guarda dados de saúde, o tipo mais sensível de dado pessoal. Esta página resume o que o sistema faz e o que a instalação precisa fazer.

## No sistema

| Proteção | Como |
|---|---|
| **Só os dados da clínica** | Toda consulta ao banco é limitada à clínica da instalação, e a pessoa precisa de um vínculo ativo para entrar |
| **Perfis** | Administrador, recepção e profissional; o profissional vê só a própria agenda e nenhum valor da clínica |
| **Senhas** | Guardadas com Argon2; no mínimo 10 caracteres, não comuns, não só números, não parecidas com o nome de usuário |
| **Bloqueio de login** | 5 senhas erradas para o mesmo usuário a partir do mesmo endereço bloqueiam por 1 hora |
| **Sessões** | Até 8 horas, terminando quando o navegador fecha; cookies `HttpOnly` e, com `DJANGO_SECURE=1`, `Secure` |
| **HTTPS** | Certificado automático (Caddy); com `DJANGO_SECURE=1`, redireciona para HTTPS e usa HSTS de um ano |
| **Content Security Policy** | Só rodam os scripts do próprio sistema; sem CDN, sem JavaScript embutido na página |
| **Auditoria** | Quem criou, alterou, excluiu ou abriu cada registro, quando e de qual endereço; não pode ser alterada |
| **Envio de arquivos** | Limitado a 6 MB |
| **Documentação da API** | `/api/v1/docs` só para superusuários |

## Privacidade (LGPD)

- **Política de privacidade** no sistema, em `/privacidade/`, nos três idiomas: o que é tratado, para quê, com qual base legal, quem tem acesso, onde fica guardado, por quanto tempo e os direitos do paciente. Adapte-a à sua clínica: a clínica é a controladora dos dados. Veja [Política de privacidade](manual/privacidade.md).
- **Pacientes arquivados** saem das listas e buscas; o administrador pode **excluir definitivamente** o paciente que pedir, mantendo a agenda e o financeiro sem a identificação dele. Veja [Pacientes](manual/pacientes.md).
- **Retenção:** tentativas de entrada recusadas são apagadas depois de 30 dias; os backups no Google Cloud, depois de 30 dias.
- **Sem rastreamento:** só os cookies de sessão e de segurança; sem analytics, sem scripts de terceiros.

## O que a instalação precisa fazer

- Deixar o `.env` legível só pelo root, com uma `DJANGO_SECRET_KEY` longa e senhas fortes. Nunca colocá-lo no Git.
- Rodar com `DJANGO_DEBUG=0`, `DJANGO_SECURE=1` e `DJANGO_PROXY_REVERSO=1` atrás do Caddy.
- Nunca rodar `popular_dados_teste` num servidor com dados reais (os usuários dele têm a mesma senha).
- Expor só as portas 80 e 443. O banco e o app escutam só dentro do servidor.
- Restringir o SSH (só com chave; no Google Cloud, só pelo túnel IAP).
- Fazer backup todo dia, guardar uma cópia fora do servidor, criptografada, e [testar a restauração](operations/backup-restore.md).
- Saber onde ficam os dados: um servidor fora do Brasil é transferência internacional pela LGPD (art. 33).
- Manter o sistema [atualizado](operations/upgrade.md).

## Como relatar uma vulnerabilidade

Por favor, **não** abra uma issue pública. Relate em particular pelo [GitHub Security Advisories](https://github.com/facchini-miguel/kaladrius/security/advisories/new), com os passos para reproduzir. A resposta vem em poucos dias.
