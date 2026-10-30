"""Treatment estimates and the procedure price list (0.18.0).

Estimates belong to the Orcamentos module (practitioners, front desk and administrators);
approving one creates a receivable, so it also needs Recebimentos (not practitioners).
Discounts follow the receivables rule: administrators only. The price list is part of the
Cadastros module (administrators change it, the others only read it).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import modulos
from apps.core.models import ModuloClinico
from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.financeiro.models import Categoria
from apps.odontologia.dentes import odontograma
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from . import servicos
from .forms import AprovarForm, DescontoForm, ItemForm, OrcamentoForm, ProcedimentoForm
from .models import Orcamento, Procedimento

POR_PAGINA = 50


def _orcamentos():
    # Archived patients leave the team's screens (decision 046).
    return Orcamento.objects.filter(paciente__arquivado=False).select_related(
        "paciente", "profissional"
    )


def _aberto(request, pk):
    orcamento = get_object_or_404(_orcamentos(), pk=pk)
    if orcamento.situacao != Orcamento.Situacao.ABERTO:
        messages.error(request, _("Este orçamento já foi aprovado ou recusado."))
        return None, redirect("orcamentos:detalhe", pk=orcamento.pk)
    return orcamento, None


def _odontologia(request):
    # The request's cached modules; the item's save() re-checks under the clinic lock.
    return ModuloClinico.ODONTOLOGIA in modulos.habilitados(request)


@exige_permissao(Modulo.ORCAMENTOS, Acao.VER)
def lista(request):
    situacao = request.GET.get("situacao", Orcamento.Situacao.ABERTO)
    busca = request.GET.get("q", "").strip()
    orcamentos = _orcamentos().prefetch_related("itens")
    if situacao in Orcamento.Situacao.values:
        orcamentos = orcamentos.filter(situacao=situacao)
    if busca:
        orcamentos = orcamentos.filter(paciente__nome__unaccent__icontains=busca)
    pagina = Paginator(orcamentos, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "orcamentos/lista.html",
        {
            "pagina": pagina,
            "situacao": situacao,
            "busca": busca,
            "situacoes": Orcamento.Situacao.choices,
            "parametros": urlencode({"situacao": situacao, "q": busca}),
        },
    )


@exige_permissao(Modulo.ORCAMENTOS, Acao.CRIAR)
def novo(request):
    inicial = {}
    codigo = request.GET.get("paciente", "")
    if codigo.isdecimal():
        inicial["paciente"] = codigo
    # A practitioner writes estimates in their own name by default.
    proprio = Profissional.objects.filter(usuario=request.user, ativo=True).first()
    if proprio is not None:
        inicial["profissional"] = proprio.pk
    form = OrcamentoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        form.instance.criado_por = request.user
        orcamento = form.save()
        messages.success(request, _("Orçamento criado. Agora inclua os procedimentos."))
        return redirect("orcamentos:detalhe", pk=orcamento.pk)
    valor_paciente = form["paciente"].value()
    paciente = (
        Paciente.objects.filter(pk=valor_paciente, arquivado=False).first()
        if str(valor_paciente or "").isdecimal()
        else None
    )
    return render(request, "orcamentos/form.html", {"form": form, "paciente": paciente})


@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def editar(request, pk):
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    form = OrcamentoForm(request.POST or None, instance=orcamento)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Orçamento salvo."))
        return redirect("orcamentos:detalhe", pk=orcamento.pk)
    return render(
        request,
        "orcamentos/form.html",
        {"form": form, "paciente": orcamento.paciente, "orcamento": orcamento},
    )


@exige_permissao(Modulo.ORCAMENTOS, Acao.VER)
def detalhe(request, pk):
    orcamento = get_object_or_404(_orcamentos().prefetch_related("itens"), pk=pk)
    aberto = orcamento.situacao == Orcamento.Situacao.ABERTO
    odontologia = _odontologia(request)
    # Whoever writes the estimate may also give a discount on its total (0.27.1, decision 074).
    pode_desconto = pode(request, Modulo.ORCAMENTOS, Acao.ALTERAR)
    return render(
        request,
        "orcamentos/detalhe.html",
        {
            "orcamento": orcamento,
            "aberto": aberto,
            "item_form": ItemForm(odontologia=odontologia),
            "odontologia_habilitada": odontologia,
            "desconto_form": DescontoForm(initial={"desconto": orcamento.desconto})
            if pode_desconto and aberto
            else None,
            "pode_aprovar": aberto
            and pode(request, Modulo.RECEBIMENTOS, Acao.CRIAR)
            and pode(request, Modulo.ORCAMENTOS, Acao.ALTERAR),
            **_dentes(request, orcamento),
        },
    )


def _dentes(request, orcamento):
    """Dental chart and tooth columns (decision 080): in the Odontologia area, and in any
    area for an estimate that already has teeth (changing the area hides nothing written)."""
    tem_historico = any(item.dentes or item.faces for item in orcamento.itens.all())
    if not (_odontologia(request) or tem_historico):
        return {"mostrar_dentes": False}
    return {"mostrar_dentes": True, **odontograma(orcamento.dentes)}


@require_POST
@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def item_adicionar(request, pk):
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    form = ItemForm(request.POST, odontologia=_odontologia(request))
    if form.is_valid():
        item = form.save(commit=False)
        item.orcamento = orcamento
        item.descricao = form.cleaned_data["descricao"]
        item.valor_unitario = form.cleaned_data["valor_unitario"]
        try:
            item.save()
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Item incluído."))
    else:
        erros = [str(erro) for lista in form.errors.values() for erro in lista]
        messages.error(request, " ".join(erros))
    return redirect("orcamentos:detalhe", pk=orcamento.pk)


@require_POST
@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def item_remover(request, pk, item):
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    registro = get_object_or_404(orcamento.itens, pk=item)
    if (registro.dentes or registro.faces) and not _odontologia(request):
        raise PermissionDenied
    try:
        registro.delete()
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
    else:
        messages.success(request, _("Item removido."))
    return redirect("orcamentos:detalhe", pk=orcamento.pk)


@require_POST
@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def desconto(request, pk):
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    form = DescontoForm(request.POST)
    if form.is_valid():
        valor = form.cleaned_data["desconto"] or 0
        if valor > orcamento.subtotal:
            messages.error(request, _("O desconto passa do total do orçamento."))
        else:
            orcamento.desconto = valor
            orcamento.save()
            messages.success(request, _("Desconto aplicado."))
    return redirect("orcamentos:detalhe", pk=orcamento.pk)


@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def aprovar(request, pk):
    if not pode(request, Modulo.RECEBIMENTOS, Acao.CRIAR):
        raise PermissionDenied
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    item = orcamento.itens.select_related("procedimento__categoria").first()
    categoria = (
        item.procedimento.categoria
        if item and item.procedimento and item.procedimento.categoria
        else Categoria.objects.filter(tipo=Categoria.Tipo.RECEITA, ativa=True).first()
    )
    form = AprovarForm(request.POST or None, initial={"categoria": categoria})
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        pagamento = (
            {"forma": dados["forma"], "conta": dados["conta"]} if dados["recebido_agora"] else None
        )
        try:
            lancamento = servicos.aprovar(
                orcamento,
                parcelas=dados["parcelas"],
                primeiro_vencimento=dados["primeiro_vencimento"],
                categoria=dados["categoria"],
                usuario=request.user,
                pagamento=pagamento,
            )
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Orçamento aprovado e lançado em A receber."))
            return redirect("financeiro:lancamento", pk=lancamento.pk)
    return render(request, "orcamentos/aprovar.html", {"form": form, "orcamento": orcamento})


@require_POST
@exige_permissao(Modulo.ORCAMENTOS, Acao.ALTERAR)
def recusar(request, pk):
    orcamento, resposta = _aberto(request, pk)
    if resposta:
        return resposta
    try:
        servicos.recusar(orcamento, usuario=request.user)
    except ValidationError as erro:  # approved or refused by someone else a moment ago
        messages.error(request, erro.messages[0])
    else:
        messages.success(request, _("Orçamento marcado como recusado."))
    return redirect("orcamentos:detalhe", pk=orcamento.pk)


@exige_permissao(Modulo.ORCAMENTOS, Acao.VER)
def imprimir(request, pk):
    orcamento = get_object_or_404(_orcamentos().prefetch_related("itens"), pk=pk)
    return render(
        request,
        "orcamentos/imprimir.html",
        {"orcamento": orcamento, **_dentes(request, orcamento)},
    )


# --- Procedure price list ---------------------------------------------------------------


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def procedimentos(request):
    return render(
        request,
        "orcamentos/procedimentos.html",
        {"procedimentos": Procedimento.objects.select_related("categoria")},
    )


@exige_permissao(Modulo.CADASTROS, Acao.ALTERAR)
def procedimento_form(request, pk=None):
    procedimento = get_object_or_404(Procedimento.objects, pk=pk) if pk else Procedimento()
    form = ProcedimentoForm(request.POST or None, instance=procedimento)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Procedimento %(nome)s salvo.") % {"nome": form.instance.nome})
        return redirect("orcamentos:procedimentos")
    return render(
        request,
        "orcamentos/procedimento_form.html",
        {"form": form, "procedimento": procedimento},
    )
