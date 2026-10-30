"""Automatic audit of creations, changes and deletions, plus logins."""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.convenios.models import Carteirinha, Convenio
from apps.core.models import Clinica, ModuloDaClinica, Vinculo
from apps.financeiro.models import (
    Caixa,
    Categoria,
    CentroCusto,
    Comissao,
    Conta,
    Fechamento,
    Fornecedor,
    GrupoContabil,
    ImportacaoExtrato,
    Lancamento,
    MovimentoCaixa,
    Pagamento,
    Parcela,
    Planejamento,
    TransacaoBancaria,
)
from apps.orcamentos.models import ItemOrcamento, Orcamento, Procedimento
from apps.pacientes.models import Paciente
from apps.pessoal.models import Folha, Funcionario, Salario
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

from .models import RegistroAuditoria
from .registro import ip_da_requisicao, registrar

Acao = RegistroAuditoria.Acao
Usuario = get_user_model()

AUDITADOS = [
    Paciente,
    Agendamento,
    Rechamada,
    Convenio,
    Carteirinha,
    Profissional,
    TipoAtendimento,
    Clinica,
    ModuloDaClinica,
    Vinculo,
    Usuario,
    Fornecedor,
    Lancamento,
    Parcela,
    Pagamento,
    Conta,
    Categoria,
    GrupoContabil,
    Planejamento,
    Funcionario,
    Salario,
    Folha,
    CentroCusto,
    Fechamento,
    Caixa,
    MovimentoCaixa,
    Comissao,
    ImportacaoExtrato,
    TransacaoBancaria,
    Procedimento,
    Orcamento,
    ItemOrcamento,
]
# Never stored (secrets) or not worth storing (bookkeeping timestamps).
IGNORADOS = {
    "password",
    "last_login",
    "criado_em",
    "criada_em",
    "alterado_em",
    "alterada_em",
    "ultima_versao_vista",
    "idioma",
}


def _campos(modelo):
    return [
        campo
        for campo in modelo._meta.concrete_fields
        if not campo.primary_key and campo.attname not in IGNORADOS and campo.name not in IGNORADOS
    ]


def _valor(campo, instancia):
    valor = campo.value_from_object(instancia)
    if valor is None or isinstance(valor, bool | int | float | str):
        return valor
    return str(valor)


def _valores(instancia):
    return {campo.name: _valor(campo, instancia) for campo in _campos(type(instancia))}


def antes_de_salvar(sender, instance, raw=False, **kwargs):
    if raw or instance.pk is None:
        instance._auditoria_antes = None
        return
    anterior = sender._base_manager.filter(pk=instance.pk).first()
    instance._auditoria_antes = _valores(anterior) if anterior is not None else None
    instance._auditoria_senha = getattr(anterior, "password", None)


def depois_de_salvar(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    depois = _valores(instance)
    antes = getattr(instance, "_auditoria_antes", None)
    if created or antes is None:
        alteracoes = {
            campo: [None, valor] for campo, valor in depois.items() if valor not in (None, "")
        }
        registrar(Acao.CRIAR, instance, alteracoes=alteracoes)
        return
    alteracoes = {
        campo: [antes.get(campo), valor]
        for campo, valor in depois.items()
        if antes.get(campo) != valor
    }
    if getattr(instance, "_auditoria_senha", None) not in (
        None,
        getattr(instance, "password", None),
    ):
        alteracoes["senha"] = ["(oculta)", "(alterada)"]  # the hash itself is never stored
    if alteracoes:
        registrar(Acao.ALTERAR, instance, alteracoes=alteracoes)


def depois_de_excluir(sender, instance, **kwargs):
    valores = {
        campo: [valor, None]
        for campo, valor in _valores(instance).items()
        if valor not in (None, "")
    }
    registrar(Acao.EXCLUIR, instance, alteracoes=valores)


for modelo in AUDITADOS:
    uid = f"auditoria_{modelo._meta.label_lower}"
    pre_save.connect(antes_de_salvar, sender=modelo, dispatch_uid=f"{uid}_pre")
    post_save.connect(depois_de_salvar, sender=modelo, dispatch_uid=f"{uid}_post")
    post_delete.connect(depois_de_excluir, sender=modelo, dispatch_uid=f"{uid}_delete")


def _entrou(sender, request, user, **kwargs):
    registrar(Acao.LOGIN, usuario=user, ip=ip_da_requisicao(request), descricao=user.get_username())


def _saiu(sender, request, user, **kwargs):
    if user is not None:
        registrar(
            Acao.LOGOUT, usuario=user, ip=ip_da_requisicao(request), descricao=user.get_username()
        )


def _falhou(sender, credentials, request=None, **kwargs):
    # Only the username is kept; the password typed is never stored.
    nome = str(credentials.get("username", ""))[:150]
    registrar(
        Acao.LOGIN_FALHOU,
        ip=ip_da_requisicao(request) if request is not None else None,
        descricao=f"usuário informado: {nome}",
    )


user_logged_in.connect(_entrou, dispatch_uid="auditoria_login")
user_logged_out.connect(_saiu, dispatch_uid="auditoria_logout")
user_login_failed.connect(_falhou, dispatch_uid="auditoria_login_falhou")
