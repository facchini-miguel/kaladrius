"""Writing audit entries. The request context (user, IP) comes from AuditoriaMiddleware."""

import contextlib
from contextvars import ContextVar

from django.conf import settings
from django.utils import translation

from apps.core.isolation import clinica_atual, isolamento_ativo

from .models import AuditEntry

_usuario = ContextVar("auditoria_usuario", default=None)
_ip = ContextVar("auditoria_ip", default=None)


@contextlib.contextmanager
def contexto(user, ip):
    tokens = (_usuario.set(user), _ip.set(ip))
    try:
        yield
    finally:
        _usuario.reset(tokens[0])
        _ip.reset(tokens[1])


def ip_da_requisicao(request):
    return request.META.get("REMOTE_ADDR") or None


def registrar(acao, objeto=None, *, clinic=None, alteracoes=None, user=None, ip=None, descricao=""):
    user = user if user is not None else _usuario.get()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    if clinic is None and objeto is not None:
        # Rows without a clinic of their own (user accounts) are filed under the clinic
        # where the change was made, so the clinic administrator sees it in the audit log.
        clinic = _clinica_de(objeto) or (clinica_atual() if isolamento_ativo() else None)
    return AuditEntry.objects.create(
        acao=acao,
        clinic_id=getattr(clinic, "pk", clinic),
        user=user,
        usuario_nome=user.get_username() if user else "",
        modelo=nome_do_modelo(type(objeto)) if objeto is not None else "",
        objeto_id=str(objeto.pk) if objeto is not None and objeto.pk is not None else "",
        objeto_descricao=(descricao or (str(objeto) if objeto is not None else ""))[:200],
        alteracoes=alteracoes or {},
        ip=ip if ip is not None else _ip.get(),
    )


def nome_do_modelo(modelo):
    """How entries name the kind of record ("Paciente", "Agendamento"...).

    Always in the source language, whatever the user's language: entries are filtered
    and anonymized by this name.
    """
    with translation.override(settings.LANGUAGE_CODE):
        return str(modelo._meta.verbose_name).capitalize()


REMOVIDO = "(removido)"


def anonimizar(modelo, ids):
    """Remove the personal data from the audit entries of these records (LGPD erasure).

    Who did what and when, the record code and the names of the changed fields stay;
    the values and the record description go.
    """
    nome = nome_do_modelo(modelo)
    registros = AuditEntry.objects.filter(modelo=nome, objeto_id__in=[str(i) for i in ids])
    for registro in registros:
        registro.objeto_descricao = f"{nome} {registro.objeto_id} (dados removidos)"
        registro.alteracoes = {campo: [REMOVIDO, REMOVIDO] for campo in registro.alteracoes}
        registro.save(update_fields=["objeto_descricao", "alteracoes"])


def _clinica_de(objeto):
    from apps.core.models import Clinic

    if isinstance(objeto, Clinic):
        return objeto.pk
    return getattr(objeto, "clinic_id", None)
