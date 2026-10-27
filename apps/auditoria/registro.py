"""Writing audit entries. The request context (user, IP) comes from AuditoriaMiddleware."""

import contextlib
from contextvars import ContextVar

from apps.core.isolamento import clinica_atual, isolamento_ativo

from .models import RegistroAuditoria

_usuario = ContextVar("auditoria_usuario", default=None)
_ip = ContextVar("auditoria_ip", default=None)


@contextlib.contextmanager
def contexto(usuario, ip):
    tokens = (_usuario.set(usuario), _ip.set(ip))
    try:
        yield
    finally:
        _usuario.reset(tokens[0])
        _ip.reset(tokens[1])


def ip_da_requisicao(request):
    return request.META.get("REMOTE_ADDR") or None


def registrar(
    acao, objeto=None, *, clinica=None, alteracoes=None, usuario=None, ip=None, descricao=""
):
    usuario = usuario if usuario is not None else _usuario.get()
    if usuario is not None and not getattr(usuario, "is_authenticated", False):
        usuario = None
    if clinica is None and objeto is not None:
        # Rows without a clinic of their own (user accounts) are filed under the clinic
        # where the change was made, so the clinic administrator sees it in the audit log.
        clinica = _clinica_de(objeto) or (clinica_atual() if isolamento_ativo() else None)
    return RegistroAuditoria.objects.create(
        acao=acao,
        clinica_id=getattr(clinica, "pk", clinica),
        usuario=usuario,
        usuario_nome=usuario.get_username() if usuario else "",
        modelo=type(objeto)._meta.verbose_name.capitalize() if objeto is not None else "",
        objeto_id=str(objeto.pk) if objeto is not None and objeto.pk is not None else "",
        objeto_descricao=(descricao or (str(objeto) if objeto is not None else ""))[:200],
        alteracoes=alteracoes or {},
        ip=ip if ip is not None else _ip.get(),
    )


def _clinica_de(objeto):
    from apps.core.models import Clinica

    if isinstance(objeto, Clinica):
        return objeto.pk
    return getattr(objeto, "clinica_id", None)
