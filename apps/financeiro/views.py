"""Receivables (0.15.0): entries, receiving payments, receipts and debtors.

Accounts and categories are managed by administrators (Financeiro module); the front desk
records entries and payments (Recebimentos module) but cannot cancel, reverse or discount.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.pacientes.models import Paciente

from . import servicos
from .forms import CategoriaForm, ContaForm, LancamentoReceberForm, MotivoForm, ReceberForm
from .models import Categoria, Conta, Lancamento, Pagamento, Parcela

POR_PAGINA = 50
SITUACOES = {
    "abertas": Q(saldo__gt=0, lancamento__cancelado=False),
    "vencidas": Q(saldo__gt=0, lancamento__cancelado=False),  # + due date before today
    "pagas": Q(saldo__lte=0, lancamento__cancelado=False),
    "todas": Q(),
}


def _receber(request):
    """Installments of receivables, with paid amount and balance."""
    return (
        Parcela.objects.com_saldo()
        .filter(lancamento__tipo=Lancamento.Tipo.RECEBER)
        .select_related("lancamento__paciente", "lancamento")
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def receber_lista(request):
    hoje = timezone.localdate()
    situacao = request.GET.get("situacao", "abertas")
    busca = request.GET.get("q", "").strip()
    parcelas = _receber(request).filter(SITUACOES.get(situacao, SITUACOES["abertas"]))
    if situacao == "vencidas":
        parcelas = parcelas.filter(vencimento__lt=hoje)
    if busca:
        parcelas = parcelas.filter(
            Q(lancamento__paciente__nome__unaccent__icontains=busca)
            | Q(lancamento__pessoa__unaccent__icontains=busca)
            | Q(lancamento__descricao__unaccent__icontains=busca)
        )
    parcelas = parcelas.order_by("vencimento", "pk")
    pagina = Paginator(parcelas, POR_PAGINA).get_page(request.GET.get("pagina"))
    for parcela in pagina:
        parcela.situacao = servicos.situacao(parcela, hoje)
    return render(
        request,
        "financeiro/receber_lista.html",
        {
            "pagina": pagina,
            "situacao": situacao,
            "busca": busca,
            "parametros": urlencode({"situacao": situacao, "q": busca}),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def lancamento_novo(request):
    inicial = {}
    codigo = request.GET.get("paciente", "")
    paciente = None
    if codigo.isdecimal():
        paciente = Paciente.objects.filter(pk=int(codigo), arquivado=False).first()
        if paciente is not None:
            inicial["paciente"] = paciente.pk
    form = LancamentoReceberForm(request.POST or None, initial=inicial, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        lancamento = servicos.criar_lancamento(
            clinica=request.clinica,
            tipo=Lancamento.Tipo.RECEBER,
            paciente=dados["paciente"],
            pessoa="" if dados["paciente"] else dados["pessoa"].strip(),
            descricao=dados["descricao"],
            categoria=dados["categoria"],
            profissional=dados["profissional"],
            observacoes=dados["observacoes"],
            valor_total=dados["valor_total"],
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            usuario=request.user,
        )
        if dados["recebido_agora"]:
            primeira = lancamento.parcelas.order_by("numero").first()
            pagamento = servicos.receber(
                primeira,
                usuario=request.user,
                valor=primeira.valor,
                forma=dados["forma"],
                conta=dados["conta"],
            )
            messages.success(request, _("Lançamento criado e 1ª parcela recebida."))
            return redirect("financeiro:recibo", pk=pagamento.pk)
        messages.success(request, _("Lançamento criado."))
        return redirect("financeiro:lancamento", pk=lancamento.pk)
    if paciente is None and form["paciente"].value():
        paciente = Paciente.objects.filter(pk=form["paciente"].value()).first()
    return render(request, "financeiro/lancamento_form.html", {"form": form, "paciente": paciente})


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def lancamento(request, pk):
    lancamento = get_object_or_404(
        Lancamento.objects.select_related("paciente", "categoria", "profissional"),
        pk=pk,
        tipo=Lancamento.Tipo.RECEBER,
    )
    hoje = timezone.localdate()
    parcelas = list(
        Parcela.objects.com_saldo().filter(lancamento=lancamento).select_related("lancamento")
    )
    pagamentos = Pagamento.objects.filter(parcela__lancamento=lancamento).select_related(
        "parcela", "conta", "criado_por"
    )
    for parcela in parcelas:
        parcela.situacao = servicos.situacao(parcela, hoje)
        parcela.lista_pagamentos = [p for p in pagamentos if p.parcela_id == parcela.pk]
    return render(
        request,
        "financeiro/lancamento.html",
        {
            "lancamento": lancamento,
            "parcelas": parcelas,
            "total_pago": sum(p.pago for p in parcelas),
            "total_saldo": sum(p.saldo for p in parcelas) if not lancamento.cancelado else 0,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def lancamento_cancelar(request, pk):
    lancamento = get_object_or_404(Lancamento.objects, pk=pk, cancelado=False)
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            servicos.cancelar(lancamento, motivo=form.cleaned_data["motivo"], usuario=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento cancelado."))
        return redirect("financeiro:lancamento", pk=lancamento.pk)
    return render(
        request,
        "financeiro/motivo.html",
        {
            "form": form,
            "titulo": _("Cancelar lançamento"),
            "objeto": lancamento,
            "voltar": lancamento.pk,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def receber(request, pk):
    parcela = get_object_or_404(
        Parcela.objects.com_saldo().select_related("lancamento__paciente"),
        pk=pk,
        lancamento__cancelado=False,
    )
    if parcela.saldo <= 0:
        messages.info(request, _("Esta parcela já está paga."))
        return redirect("financeiro:lancamento", pk=parcela.lancamento_id)
    pode_desconto = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR)
    conta_padrao = Conta.objects.filter(ativa=True, tipo=Conta.Tipo.DINHEIRO).first()
    form = ReceberForm(
        request.POST or None,
        initial={"valor": parcela.saldo, "data": timezone.localdate(), "conta": conta_padrao},
        pode_dar_desconto=pode_desconto,
    )
    if request.method == "POST" and form.is_valid():
        dados = {campo: valor for campo, valor in form.cleaned_data.items() if campo in form.fields}
        dados.setdefault("desconto", 0)
        dados["juros"] = dados.get("juros") or 0
        try:
            pagamento = servicos.receber(parcela, usuario=request.user, **dados)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Pagamento registrado."))
            return redirect("financeiro:recibo", pk=pagamento.pk)
    return render(
        request,
        "financeiro/receber.html",
        {
            "form": form,
            "parcela": parcela,
            "total_parcelas": parcela.lancamento.parcelas.count(),
            "pode_desconto": pode_desconto,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def recibo(request, pk):
    pagamento = get_object_or_404(
        Pagamento.objects.select_related("parcela__lancamento__paciente", "conta", "criado_por"),
        pk=pk,
        parcela__lancamento__tipo=Lancamento.Tipo.RECEBER,
    )
    return render(
        request,
        "financeiro/recibo.html",
        {
            "pagamento": pagamento,
            "lancamento": pagamento.parcela.lancamento,
            "total_parcelas": pagamento.parcela.lancamento.parcelas.count(),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def estornar(request, pk):
    pagamento = get_object_or_404(
        Pagamento.objects.select_related("parcela__lancamento"), pk=pk, estornado=False
    )
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        servicos.estornar(pagamento, motivo=form.cleaned_data["motivo"], usuario=request.user)
        messages.success(request, _("Pagamento estornado."))
        return redirect("financeiro:lancamento", pk=pagamento.parcela.lancamento_id)
    return render(
        request,
        "financeiro/motivo.html",
        {
            "form": form,
            "titulo": _("Estornar pagamento"),
            "objeto": pagamento,
            "voltar": pagamento.parcela.lancamento_id,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def devedores(request):
    linhas = servicos.devedores()
    return render(
        request,
        "financeiro/devedores.html",
        {
            "linhas": linhas,
            "total_vencido": sum(linha["vencido"] for linha in linhas),
            "total_a_vencer": sum(linha["a_vencer"] for linha in linhas),
        },
    )


# --- Accounts and categories (administrators) -----------------------------------------


CADASTROS = {
    "categorias": (Categoria, CategoriaForm),
    "contas": (Conta, ContaForm),
}


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def cadastro_lista(request, cadastro):
    modelo, _form = CADASTROS[cadastro]
    return render(
        request,
        "financeiro/cadastro_lista.html",
        {"cadastro": cadastro, "itens": modelo.objects.all(), "modelo": modelo._meta},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def cadastro_form(request, cadastro, pk=None):
    modelo, classe = CADASTROS[cadastro]
    instancia = get_object_or_404(modelo.objects, pk=pk) if pk else modelo()
    form = classe(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": form.instance.nome})
        return redirect("financeiro:cadastro", cadastro=cadastro)
    return render(
        request,
        "financeiro/cadastro_form.html",
        {"form": form, "cadastro": cadastro, "instancia": instancia, "modelo": modelo._meta},
    )
