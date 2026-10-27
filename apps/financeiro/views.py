"""Finance: receivables (0.15.0), payables, cash flow and reports (0.16.0).

Receivables belong to the Recebimentos module (administrators and the front desk, which
cannot cancel, reverse or discount). Payables, accounts, categories, cash flow and reports
belong to the Financeiro module (administrators). Entries and payments of both kinds share
the same screens; each view checks the module of the entry's kind.
"""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.pacientes.models import Paciente

from . import servicos
from .forms import (
    CategoriaForm,
    ContaForm,
    LancamentoPagarForm,
    LancamentoReceberForm,
    MotivoForm,
    ReceberForm,
)
from .models import Categoria, Conta, Lancamento, Pagamento, Parcela

POR_PAGINA = 50
SITUACOES = {
    "abertas": Q(saldo__gt=0, lancamento__cancelado=False),
    "vencidas": Q(saldo__gt=0, lancamento__cancelado=False),  # + due date before today
    "pagas": Q(saldo__lte=0, lancamento__cancelado=False),
    "todas": Q(),
}


def _modulo(tipo):
    return Modulo.RECEBIMENTOS if tipo == Lancamento.Tipo.RECEBER else Modulo.FINANCEIRO


def _exigir(request, tipo, acao):
    """Payables need the Financeiro module (administrators) for the same action."""
    if not pode(request, _modulo(tipo), acao):
        raise PermissionDenied


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def receber_lista(request):
    return _lista(request, Lancamento.Tipo.RECEBER)


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def pagar_lista(request):
    return _lista(request, Lancamento.Tipo.PAGAR)


def _lista(request, tipo):
    hoje = timezone.localdate()
    situacao = request.GET.get("situacao", "abertas")
    busca = request.GET.get("q", "").strip()
    parcelas = (
        Parcela.objects.com_saldo()
        .filter(lancamento__tipo=tipo)
        .select_related("lancamento__paciente", "lancamento")
        .filter(SITUACOES.get(situacao, SITUACOES["abertas"]))
    )
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
        "financeiro/lista.html",
        {
            "tipo": tipo,
            "pagar": tipo == Lancamento.Tipo.PAGAR,
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


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def despesa_nova(request):
    form = LancamentoPagarForm(request.POST or None, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        lancamento = servicos.criar_lancamento(
            clinica=request.clinica,
            tipo=Lancamento.Tipo.PAGAR,
            pessoa=dados["pessoa"].strip(),
            descricao=dados["descricao"],
            categoria=dados["categoria"],
            observacoes=dados["observacoes"],
            valor_total=form.valor_total(),
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            usuario=request.user,
        )
        if dados["pago_agora"]:
            primeira = lancamento.parcelas.order_by("numero").first()
            servicos.receber(
                primeira,
                usuario=request.user,
                valor=primeira.valor,
                forma=dados["forma"],
                conta=dados["conta"],
            )
        messages.success(request, _("Despesa lançada."))
        return redirect("financeiro:lancamento", pk=lancamento.pk)
    return render(request, "financeiro/despesa_form.html", {"form": form})


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def lancamento(request, pk):
    lancamento = get_object_or_404(
        Lancamento.objects.select_related("paciente", "categoria", "profissional"), pk=pk
    )
    _exigir(request, lancamento.tipo, Acao.VER)
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
            "pagar": lancamento.tipo == Lancamento.Tipo.PAGAR,
            "pode_alterar": pode(request, _modulo(lancamento.tipo), Acao.CRIAR),
            "pode_excluir": pode(request, _modulo(lancamento.tipo), Acao.EXCLUIR),
            "parcelas": parcelas,
            "total_pago": sum(p.pago for p in parcelas),
            "total_saldo": sum(p.saldo for p in parcelas) if not lancamento.cancelado else 0,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def lancamento_cancelar(request, pk):
    lancamento = get_object_or_404(Lancamento.objects, pk=pk, cancelado=False)
    _exigir(request, lancamento.tipo, Acao.EXCLUIR)
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
    _exigir(request, parcela.lancamento.tipo, Acao.CRIAR)
    pagar = parcela.lancamento.tipo == Lancamento.Tipo.PAGAR
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
    if pagar:
        form.fields["valor"].label = _("Valor pago")
        form.fields["juros"].help_text = _("Já incluídos no valor pago.")
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
            if pagar:
                return redirect("financeiro:lancamento", pk=parcela.lancamento_id)
            return redirect("financeiro:recibo", pk=pagamento.pk)
    return render(
        request,
        "financeiro/receber.html",
        {
            "form": form,
            "parcela": parcela,
            "total_parcelas": parcela.lancamento.parcelas.count(),
            "pode_desconto": pode_desconto,
            "pagar": pagar,
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
    _exigir(request, pagamento.parcela.lancamento.tipo, Acao.EXCLUIR)
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


# --- Cash flow and reports (administrators) ---------------------------------------------


def _periodo(request):
    """(de, ate) from the query string; the current month by default (at most 2 years)."""
    hoje = timezone.localdate()
    inicio_do_mes = hoje.replace(day=1)
    fim_do_mes = servicos.somar_meses(inicio_do_mes, 1) - datetime.timedelta(days=1)
    try:
        de = datetime.date.fromisoformat(request.GET.get("de", ""))
    except ValueError:
        de = inicio_do_mes
    try:
        ate = datetime.date.fromisoformat(request.GET.get("ate", ""))
    except ValueError:
        ate = fim_do_mes
    if ate < de or (ate - de).days > 731:
        de, ate = inicio_do_mes, fim_do_mes
    return de, ate


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fluxo_de_caixa(request):
    de, ate = _periodo(request)
    por_mes = request.GET.get("agrupar") == "mes"
    return render(
        request,
        "financeiro/fluxo.html",
        {
            "de": de,
            "ate": ate,
            "por_mes": por_mes,
            "fluxo": servicos.fluxo_de_caixa(de, ate, por_mes=por_mes),
            "contas": servicos.saldos_das_contas(),
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def relatorios(request):
    de, ate = _periodo(request)
    return render(
        request,
        "financeiro/relatorios.html",
        {"de": de, "ate": ate, "relatorio": servicos.relatorio(de, ate)},
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
