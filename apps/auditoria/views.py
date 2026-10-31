import datetime

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .models import RegistroAuditoria
from .registro import nome_do_modelo

POR_PAGINA = 100


def _data(valor):
    try:
        return datetime.date.fromisoformat(valor or "")
    except ValueError:
        return None


def tipos_de_registro():
    """Kinds of record in the filter: the audited models and the medical record documents
    (logged by hand). Asking the database took most of the page's time once the log had
    hundreds of thousands of entries (volume test, decision 108)."""
    from apps.prontuario.models import Adendo, Anexo, Atendimento, Atestado, PedidoDeExames, Receita

    from .signals import AUDITADOS

    documentos = [Atendimento, Adendo, Atestado, Receita, PedidoDeExames, Anexo]
    return sorted({nome_do_modelo(modelo) for modelo in [*AUDITADOS, *documentos]})


@exige_permissao(Modulo.AUDITORIA, Acao.VER)
def lista(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    registros = RegistroAuditoria.objects.filter(clinica=request.clinica)
    filtros = {
        "q": request.GET.get("q", "").strip(),
        "acao": request.GET.get("acao", ""),
        "modelo": request.GET.get("modelo", ""),
        "de": request.GET.get("de", ""),
        "ate": request.GET.get("ate", ""),
    }
    modelos = tipos_de_registro()
    if filtros["q"]:
        registros = registros.filter(
            Q(usuario_nome__icontains=filtros["q"])
            | Q(objeto_descricao__icontains=filtros["q"])
            | Q(objeto_id=filtros["q"])
        )
    if filtros["acao"] in RegistroAuditoria.Acao.values:
        registros = registros.filter(acao=filtros["acao"])
    if filtros["modelo"]:
        registros = registros.filter(modelo=filtros["modelo"])
    if de := _data(filtros["de"]):
        registros = registros.filter(momento__date__gte=de)
    if ate := _data(filtros["ate"]):
        registros = registros.filter(momento__date__lte=ate)
    pagina = Paginator(registros, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "auditoria/lista.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "parametros": urlencode(filtros),
            "acoes": RegistroAuditoria.Acao.choices,
            "modelos": modelos,
        },
    )
