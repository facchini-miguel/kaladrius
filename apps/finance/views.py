"""Finance: receivables (0.15.0), payables, cash flow and reports (0.16.0), commission (0.19.0),
bank statement import (0.20.0).

Receivables belong to the Recebimentos module (administrators and the front desk, which
cannot cancel, reverse or discount). Payables, accounts, categories, cash flow and reports
belong to the Financeiro module (administrators). Entries and payments of both kinds share
the same screens; each view checks the module of the entry's kind.
"""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from apps.core import legislation
from apps.core.ordering import chave_alfabetica
from apps.core.permissions import Acao, Modulo, exige_permissao, pode
from apps.core.templatetags.formats import moeda
from apps.core.validators import normalizar_cnpj
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import commissions, reconciliation, services
from .forms import (
    AbrirCaixaForm,
    CategoriaForm,
    CentroCustoForm,
    ContaForm,
    FecharCaixaForm,
    FecharForm,
    FornecedorForm,
    GrupoContabilForm,
    ImportarExtratoForm,
    LancamentoDaTransacaoForm,
    LancamentoPagarForm,
    LancamentoReceberForm,
    MotivoForm,
    MovimentoCaixaForm,
    PagarComissaoForm,
    PercentualComissaoForm,
    PlanejamentoForm,
    ReabrirForm,
    ReceberForm,
)
from .models import (
    ZERO,
    AccountGroup,
    BankTransaction,
    BookClosing,
    CashMovement,
    CashRegister,
    Category,
    Commission,
    CostCenter,
    Entry,
    FinancialAccount,
    Installment,
    Payment,
    Planning,
    StatementImport,
    Supplier,
)
from .ofx import ArquivoInvalido

POR_PAGINA = 50
SITUACOES = {
    "abertas": Q(saldo__gt=0, lancamento__cancelado=False),
    "vencidas": Q(saldo__gt=0, lancamento__cancelado=False),  # + due date before today
    "pagas": Q(saldo__lte=0, lancamento__cancelado=False),
    "todas": Q(),
}


def _modulo(tipo):
    return Modulo.RECEBIMENTOS if tipo == Entry.Tipo.RECEBER else Modulo.FINANCEIRO


def _exigir(request, tipo, acao):
    """Payables need the Financeiro module (administrators) for the same action."""
    if not pode(request, _modulo(tipo), acao):
        raise PermissionDenied


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def receber_lista(request):
    return _lista(request, Entry.Tipo.RECEBER)


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def pagar_lista(request):
    return _lista(request, Entry.Tipo.PAGAR)


def _lista(request, tipo):
    hoje = timezone.localdate()
    situacao = request.GET.get("situacao", "abertas")
    busca = request.GET.get("q", "").strip()
    parcelas = (
        Installment.objects.com_saldo()
        .filter(lancamento__tipo=tipo)
        .select_related("lancamento__patient", "lancamento")
        .filter(SITUACOES.get(situacao, SITUACOES["abertas"]))
    )
    if situacao == "vencidas":
        parcelas = parcelas.filter(vencimento__lt=hoje)
    if busca:
        parcelas = parcelas.filter(
            Q(lancamento__patient__nome__unaccent__icontains=busca)
            | Q(lancamento__pessoa__unaccent__icontains=busca)
            | Q(lancamento__descricao__unaccent__icontains=busca)
        )
    parcelas = parcelas.order_by("vencimento", "pk")
    pagina = Paginator(parcelas, POR_PAGINA).get_page(request.GET.get("pagina"))
    for parcela in pagina:
        parcela.situacao = services.situacao(parcela, hoje)
    return render(
        request,
        "finance/list.html",
        {
            "tipo": tipo,
            "pagar": tipo == Entry.Tipo.PAGAR,
            "pagina": pagina,
            "situacao": situacao,
            "busca": busca,
            "parametros": urlencode({"situacao": situacao, "q": busca}),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def lancamento_novo(request):
    inicial = {}
    codigo = request.GET.get("patient", "")
    patient = None
    if codigo.isdecimal():
        patient = Patient.objects.filter(pk=int(codigo), arquivado=False).first()
        if patient is not None:
            inicial["patient"] = patient.pk
    form = LancamentoReceberForm(request.POST or None, initial=inicial, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        lancamento = services.criar_lancamento(
            clinic=request.clinic,
            tipo=Entry.Tipo.RECEBER,
            patient=dados["patient"],
            pessoa="" if dados["patient"] else dados["pessoa"].strip(),
            descricao=dados["descricao"],
            categoria=dados["categoria"],
            centro_custo=dados.get("centro_custo"),
            practitioner=dados["practitioner"],
            observacoes=dados["observacoes"],
            valor_total=dados["valor_total"],
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            user=request.user,
        )
        if dados["recebido_agora"]:
            primeira = lancamento.parcelas.order_by("numero").first()
            pagamento = services.receber(
                primeira,
                user=request.user,
                valor=primeira.valor,
                forma=dados["forma"],
                conta=dados["conta"],
            )
            messages.success(request, _("Lançamento criado e 1ª parcela recebida."))
            return redirect("finance:receipt", pk=pagamento.pk)
        messages.success(request, _("Lançamento criado."))
        return redirect("finance:entry", pk=lancamento.pk)
    if patient is None and form["patient"].value():
        patient = Patient.objects.filter(pk=form["patient"].value()).first()
    return render(request, "finance/entry_form.html", {"form": form, "patient": patient})


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def despesa_nova(request):
    form = LancamentoPagarForm(
        request.POST or None,
        clinic=request.clinic,
        initial={"fornecedor": request.GET.get("fornecedor")},
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        lancamento = services.criar_lancamento(
            clinic=request.clinic,
            tipo=Entry.Tipo.PAGAR,
            fornecedor=dados["fornecedor"],
            pessoa=dados["pessoa"].strip(),
            descricao=dados["descricao"],
            categoria=dados["categoria"],
            centro_custo=dados.get("centro_custo"),
            observacoes=dados["observacoes"],
            valor_total=form.valor_total(),
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            user=request.user,
        )
        if dados["pago_agora"]:
            primeira = lancamento.parcelas.order_by("numero").first()
            services.receber(
                primeira,
                user=request.user,
                valor=primeira.valor,
                forma=dados["forma"],
                conta=dados["conta"],
            )
        messages.success(request, _("Despesa lançada."))
        return redirect("finance:entry", pk=lancamento.pk)
    return render(request, "finance/expense_form.html", {"form": form})


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def lancamento(request, pk):
    lancamento = get_object_or_404(
        Entry.objects.select_related("patient", "categoria", "centro_custo", "practitioner"),
        pk=pk,
    )
    _exigir(request, lancamento.tipo, Acao.VER)
    hoje = timezone.localdate()
    parcelas = list(
        Installment.objects.com_saldo().filter(lancamento=lancamento).select_related("lancamento")
    )
    pagamentos = Payment.objects.filter(parcela__lancamento=lancamento).select_related(
        "parcela", "conta", "created_by"
    )
    for parcela in parcelas:
        parcela.situacao = services.situacao(parcela, hoje)
        parcela.lista_pagamentos = [p for p in pagamentos if p.parcela_id == parcela.pk]
    return render(
        request,
        "finance/entry.html",
        {
            "lancamento": lancamento,
            "pagar": lancamento.tipo == Entry.Tipo.PAGAR,
            "pode_alterar": pode(request, _modulo(lancamento.tipo), Acao.CRIAR),
            "pode_excluir": pode(request, _modulo(lancamento.tipo), Acao.EXCLUIR),
            "parcelas": parcelas,
            "total_pago": sum(p.pago for p in parcelas),
            "total_saldo": sum(p.saldo for p in parcelas) if not lancamento.cancelado else 0,
            "comissao": Commission.objects.filter(lancamento=lancamento).first(),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def lancamento_cancelar(request, pk):
    lancamento = get_object_or_404(Entry.objects, pk=pk, cancelado=False)
    _exigir(request, lancamento.tipo, Acao.EXCLUIR)
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.cancelar(lancamento, motivo=form.cleaned_data["motivo"], user=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento cancelado."))
        return redirect("finance:entry", pk=lancamento.pk)
    return render(
        request,
        "finance/reason.html",
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
        Installment.objects.com_saldo().select_related("lancamento__patient"),
        pk=pk,
        lancamento__cancelado=False,
    )
    _exigir(request, parcela.lancamento.tipo, Acao.CRIAR)
    pagar = parcela.lancamento.tipo == Entry.Tipo.PAGAR
    if parcela.saldo <= 0:
        messages.info(request, _("Esta parcela já está paga."))
        return redirect("finance:entry", pk=parcela.lancamento_id)
    pode_desconto = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR)
    conta_padrao = FinancialAccount.objects.filter(
        ativa=True, tipo=FinancialAccount.Tipo.DINHEIRO
    ).first()
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
            pagamento = services.receber(parcela, user=request.user, **dados)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Pagamento registrado."))
            if pagar:
                return redirect("finance:entry", pk=parcela.lancamento_id)
            return redirect("finance:receipt", pk=pagamento.pk)
    return render(
        request,
        "finance/receive.html",
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
        Payment.objects.select_related(
            "parcela__lancamento__patient",
            "parcela__lancamento__practitioner",
            "conta",
            "created_by",
        ),
        pk=pk,
        parcela__lancamento__tipo=Entry.Tipo.RECEBER,
    )
    return render(
        request,
        "finance/receipt.html",
        {
            "pagamento": pagamento,
            "lancamento": pagamento.parcela.lancamento,
            "total_parcelas": pagamento.parcela.lancamento.parcelas.count(),
            # Where a tax document is required, the receipt says it does not replace it.
            "documento_fiscal": legislation.do_pais().fiscal,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def estornar(request, pk):
    pagamento = get_object_or_404(
        Payment.objects.select_related("parcela__lancamento"), pk=pk, estornado=False
    )
    _exigir(request, pagamento.parcela.lancamento.tipo, Acao.EXCLUIR)
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.estornar(pagamento, motivo=form.cleaned_data["motivo"], user=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Pagamento estornado."))
        return redirect("finance:entry", pk=pagamento.parcela.lancamento_id)
    return render(
        request,
        "finance/reason.html",
        {
            "form": form,
            "titulo": _("Estornar pagamento"),
            # Not str(pagamento): that has the raw amount ("1350.00"), for the audit log.
            "objeto": " · ".join(
                [
                    str(pagamento.parcela),
                    moeda(pagamento.valor),
                    date_format(pagamento.data, "SHORT_DATE_FORMAT"),
                ]
            ),
            "voltar": pagamento.parcela.lancamento_id,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def devedores(request):
    linhas = services.devedores()
    busca = request.GET.get("q", "").strip()
    encontrados = linhas
    if busca:
        termo = chave_alfabetica(busca)
        encontrados = [linha for linha in linhas if termo in chave_alfabetica(linha["nome"])]
    # A clinic with years of use has thousands of debtors: one page held them all (volume
    # test, decision 108). The totals still add up everyone.
    pagina = Paginator(encontrados, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/debtors.html",
        {
            "pagina": pagina,
            "busca": busca,
            "parametros": urlencode({"q": busca}),
            "total_vencido": sum(linha["vencido"] for linha in linhas),
            "total_a_vencer": sum(linha["a_vencer"] for linha in linhas),
        },
    )


# --- Daily cash drawer (0.17.0) ---------------------------------------------------------


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def caixa(request):
    """The drawer of a cash account: its open session, or the form to open it."""
    contas = list(FinancialAccount.objects.filter(tipo=FinancialAccount.Tipo.DINHEIRO, ativa=True))
    escolhida = request.GET.get("conta", "")
    conta = next((c for c in contas if str(c.pk) == escolhida), contas[0] if contas else None)
    if conta is not None:
        aberto = services.caixa_aberto(conta)
        if aberto is not None:
            return redirect("finance:cash_detail", pk=aberto.pk)
    saldo = dict(services.saldos_das_contas()).get(conta) if conta else None
    # Empty on purpose: the opening amount is what is counted, not the system balance.
    form = AbrirCaixaForm(request.POST or None)
    if request.method == "POST" and conta is not None:
        if not pode(request, Modulo.RECEBIMENTOS, Acao.CRIAR):
            raise PermissionDenied
        if form.is_valid():
            try:
                novo = services.abrir_caixa(
                    conta, valor=form.cleaned_data["valor"], user=request.user
                )
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
                return redirect(f"{request.path}?conta={conta.pk}")
            messages.success(request, _("Caixa aberto."))
            return redirect("finance:cash_detail", pk=novo.pk)
    historico = CashRegister.objects.filter(conta=conta).select_related(
        "aberto_por", "fechado_por"
    )[:30]
    return render(
        request,
        "finance/cash.html",
        {
            "contas": contas,
            "conta": conta,
            "form": form,
            "saldo_sistema": saldo,
            "historico": historico,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def caixa_detalhe(request, pk):
    sessao = get_object_or_404(
        CashRegister.objects.select_related("conta", "aberto_por", "fechado_por"), pk=pk
    )
    return render(
        request,
        "finance/cash_detail.html",
        {"caixa": sessao, "resumo": services.resumo_do_caixa(sessao)},
    )


# The kind of cash movement in the URL (decision 155) and the value the database stores.
MOVIMENTOS_NA_URL = {
    "withdrawal": CashMovement.Tipo.RETIRADA,
    "top-up": CashMovement.Tipo.REFORCO,
}


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_movimento(request, pk, tipo):
    sessao = get_object_or_404(CashRegister.objects.select_related("conta"), pk=pk, fechado_em=None)
    if tipo not in MOVIMENTOS_NA_URL:
        raise Http404
    tipo = MOVIMENTOS_NA_URL[tipo]
    form = MovimentoCaixaForm(request.POST or None, caixa=sessao)
    if request.method == "POST" and form.is_valid():
        try:
            services.movimentar_caixa(sessao, tipo=tipo, user=request.user, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Movimento registrado."))
            return redirect("finance:cash_detail", pk=sessao.pk)
    return render(
        request,
        "finance/cash_form.html",
        {"caixa": sessao, "form": form, "titulo": CashMovement.Tipo(tipo).label},
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_fechar(request, pk):
    sessao = get_object_or_404(CashRegister.objects.select_related("conta"), pk=pk, fechado_em=None)
    form = FecharCaixaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.fechar_caixa(sessao, user=request.user, **form.cleaned_data)
        messages.success(request, _("Caixa fechado."))
        return redirect("finance:cash_detail", pk=sessao.pk)
    return render(
        request,
        "finance/cash_form.html",
        {
            "caixa": sessao,
            "form": form,
            "titulo": _("Fechar caixa"),
            "esperado": services.resumo_do_caixa(sessao)["esperado"],
        },
    )


# --- Cash flow and reports (administrators) ---------------------------------------------


def _periodo(request):
    """(de, ate) from the query string; the current month by default (at most 2 years)."""
    hoje = timezone.localdate()
    inicio_do_mes = hoje.replace(day=1)
    fim_do_mes = services.somar_meses(inicio_do_mes, 1) - datetime.timedelta(days=1)
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
        "finance/cash_flow.html",
        {
            "de": de,
            "ate": ate,
            "por_mes": por_mes,
            "fluxo": services.fluxo_de_caixa(de, ate, por_mes=por_mes),
            "contas": services.saldos_das_contas(),
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def relatorios(request):
    de, ate = _periodo(request)
    return render(
        request,
        "finance/reports.html",
        {
            "de": de,
            "ate": ate,
            "relatorio": services.relatorio(de, ate),
            "fechado_ate": services.fechado_ate(request.clinic.pk),
        },
    )


# --- Yearly planning (decision 098) ---------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def planejamento(request):
    """Goals of the year per group of the chart of accounts, next to what was done."""
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano", hoje.year))
    except ValueError:
        ano = hoje.year
    ano = min(max(ano, 2000), hoje.year + 5)
    pode_alterar = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR)
    grupos = services.ligar_grupos(AccountGroup.objects.filter(ativo=True))
    metas = dict(Planning.objects.filter(ano=ano).values_list("grupo_id", "valor"))
    form = PlanejamentoForm(request.POST or None, grupos=grupos, metas=metas)
    if request.method == "POST":
        if not pode_alterar:
            raise PermissionDenied
        if request.POST.get("acao") == "copiar":
            copiadas = services.copiar_metas(ano)
            messages.success(
                request,
                ngettext(
                    "%(n)s meta copiada do ano anterior.",
                    "%(n)s metas copiadas do ano anterior.",
                    copiadas,
                )
                % {"n": copiadas},
            )
            return redirect(f"{reverse('finance:planning')}?ano={ano}")
        if form.is_valid():
            services.salvar_metas(ano, form.valores())
            messages.success(request, _("Planejamento salvo."))
            return redirect(f"{reverse('finance:planning')}?ano={ano}")
    dados = services.planejamento(ano)
    for secao in dados["secoes"]:
        for linha in secao["linhas"]:
            if pode_alterar and linha["grupo"].ativo:
                linha["campo"] = form[PlanejamentoForm.nome(linha["grupo"])]
    return render(
        request,
        "finance/planning.html",
        {
            **dados,
            "form": form,
            "pode_alterar": pode_alterar,
            "ano_anterior": ano - 1,
            "proximo_ano": ano + 1,
            "tem_metas_anteriores": Planning.objects.filter(ano=ano - 1).exists(),
        },
    )


# --- Closing the books (decision 096) -------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fechamento(request):
    """Close the books up to a date, or reopen them with a reason. Public demo logins only
    look: one visitor closing the books would block everyone else's payments."""
    demonstracao = request.user.demonstracao
    pode_fechar = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR) and not demonstracao
    pode_reabrir = pode(request, Modulo.FINANCEIRO, Acao.EXCLUIR) and not demonstracao
    if request.method == "POST":
        acao = request.POST.get("acao")
        if not {"fechar": pode_fechar, "reabrir": pode_reabrir}.get(acao):
            raise PermissionDenied
        form = (FecharForm if acao == "fechar" else ReabrirForm)(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            try:
                if acao == "fechar":
                    services.fechar(request.clinic, dados["ate"], user=request.user)
                    messages.success(request, _("Financeiro fechado."))
                else:
                    services.reabrir(
                        request.clinic, dados["ate"], motivo=dados["motivo"], user=request.user
                    )
                    messages.success(request, _("Período reaberto."))
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
        return redirect("finance:closing")
    return render(
        request,
        "finance/closing.html",
        {
            "fechado_ate": services.fechado_ate(request.clinic.pk),
            "historico": BookClosing.objects.select_related("created_by")[:30],
            "fechar_form": FecharForm() if pode_fechar else None,
            "reabrir_form": ReabrirForm() if pode_reabrir else None,
        },
    )


# --- Accounts, categories and cost centers (administrators) ----------------------------


CADASTROS = {
    "categories": (Category, CategoriaForm),
    "accounts": (FinancialAccount, ContaForm),
    "cost-centers": (CostCenter, CentroCustoForm),
}


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def cadastro_lista(request, cadastro):
    modelo, _form = CADASTROS[cadastro]
    return render(
        request,
        "finance/catalog_list.html",
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
        return redirect("finance:catalog", cadastro=cadastro)
    return render(
        request,
        "finance/catalog_form.html",
        {"form": form, "cadastro": cadastro, "instancia": instancia, "modelo": modelo._meta},
    )


# --- Chart of accounts (decision 097) ---------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def plano_contas(request):
    """The chart of accounts as a tree: groups, subgroups and their categories."""
    grupos = services.ligar_grupos(AccountGroup.objects.all())
    categorias = list(Category.objects.all())
    arvores = []
    for tipo, rotulo in Category.Tipo.choices:
        linhas = []

        def descer(pai_id, nivel, tipo=tipo, linhas=linhas):
            for grupo in (g for g in grupos if g.tipo == tipo and g.pai_id == pai_id):
                linhas.append({"nivel": nivel, "grupo": grupo})
                linhas.extend(
                    {"nivel": nivel + 1, "categoria": c}
                    for c in categorias
                    if c.grupo_id == grupo.pk
                )
                descer(grupo.pk, nivel + 1)

        descer(None, 0)
        sem_grupo = [c for c in categorias if c.tipo == tipo and c.grupo_id is None]
        arvores.append({"rotulo": rotulo, "linhas": linhas, "sem_grupo": sem_grupo})
    return render(request, "finance/chart_of_accounts.html", {"arvores": arvores})


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def grupo_novo(request):
    return _grupo_form(request, AccountGroup(tipo=request.GET.get("tipo") or None))


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def grupo_editar(request, pk):
    return _grupo_form(request, get_object_or_404(AccountGroup.objects, pk=pk))


def _grupo_form(request, instancia):
    form = GrupoContabilForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        grupo = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": grupo.nome})
        return redirect("finance:chart_of_accounts")
    return render(request, "finance/group_form.html", {"form": form, "instancia": instancia})


# --- Suppliers (decision 093) ---------------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fornecedores(request):
    busca = request.GET.get("q", "").strip()
    lista = Supplier.objects.all()
    if busca:
        filtro = Q(nome__unaccent__icontains=busca) | Q(razao_social__unaccent__icontains=busca)
        documento = normalizar_cnpj(busca)
        if any(c.isdigit() for c in documento):
            filtro |= Q(cpf_cnpj__startswith=documento)
        lista = lista.filter(filtro)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/suppliers.html",
        {"pagina": pagina, "busca": busca, "parametros": urlencode({"q": busca})},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fornecedor(request, pk):
    fornecedor = get_object_or_404(Supplier.objects, pk=pk)
    hoje = timezone.localdate()
    parcelas = list(
        Installment.objects.com_saldo()
        .filter(lancamento__fornecedor=fornecedor)
        .select_related("lancamento")
        .order_by("-vencimento", "-pk")[:POR_PAGINA]
    )
    for parcela in parcelas:
        parcela.situacao = services.situacao(parcela, hoje)
    em_aberto = sum(
        (p.saldo for p in Installment.objects.abertas().filter(lancamento__fornecedor=fornecedor)),
        start=ZERO,
    )
    return render(
        request,
        "finance/supplier.html",
        {"fornecedor": fornecedor, "parcelas": parcelas, "em_aberto": em_aberto},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def fornecedor_novo(request):
    return _fornecedor_form(request, Supplier())


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def fornecedor_editar(request, pk):
    return _fornecedor_form(request, get_object_or_404(Supplier.objects, pk=pk))


def _fornecedor_form(request, instancia):
    form = FornecedorForm(request.POST or None, instance=instancia, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        fornecedor = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": fornecedor.nome})
        return redirect("finance:supplier", pk=fornecedor.pk)
    return render(request, "finance/supplier_form.html", {"form": form, "instancia": instancia})


# --- Practitioner commission (0.19.0) --------------------------------------------------


def _ate(request):
    hoje = timezone.localdate()
    try:
        return min(datetime.date.fromisoformat(request.GET.get("ate", "")), hoje)
    except ValueError:
        return hoje


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def comissoes_lista(request):
    ate = _ate(request)
    return render(
        request,
        "finance/commissions.html",
        {
            "ate": ate,
            "linhas": commissions.resumo(ate),
            "sem_percentual": Practitioner.objects.filter(ativo=True, comissao_percentual=0),
            "historico": Commission.objects.select_related("practitioner", "lancamento")[:30],
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def comissao_percentual(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    form = PercentualComissaoForm(request.POST or None, instance=practitioner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Percentual de %(nome)s salvo.") % {"nome": practitioner.nome})
        return redirect("finance:commissions")
    return render(
        request,
        "finance/commission_percentage.html",
        {"form": form, "practitioner": practitioner},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def comissao_pagar(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    ate = _ate(request)
    padrao = (
        Category.objects.filter(tipo=Category.Tipo.DESPESA, nome="Comissões", ativa=True).first()
        or Category.objects.filter(tipo=Category.Tipo.DESPESA, ativa=True).first()
    )
    form = PagarComissaoForm(request.POST or None, initial={"categoria": padrao})
    if request.method == "POST" and form.is_valid():
        try:
            comissao = commissions.pagar(
                practitioner, ate=ate, user=request.user, **form.cleaned_data
            )
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
            return redirect(f"{reverse('finance:commissions')}?ate={ate.isoformat()}")
        messages.success(request, _("Comissão lançada em A pagar."))
        return redirect("finance:entry", pk=comissao.lancamento_id)
    return render(
        request,
        "finance/commission_pay.html",
        {"form": form, "calculo": commissions.pendente(practitioner, ate), "ate": ate},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def comissao(request, pk):
    comissao = get_object_or_404(
        Commission.objects.select_related("practitioner", "lancamento"), pk=pk
    )
    pagamentos = comissao.pagamentos.select_related("parcela__lancamento__patient").order_by(
        "data", "pk"
    )
    estornos = comissao.pagamentos_estornados.select_related(
        "parcela__lancamento__patient", "comissao"
    ).order_by("data", "pk")
    for estorno in estornos:
        estorno.comissao_devolvida = commissions.percentual_de(
            estorno.valor, estorno.comissao.percentual
        )
    return render(
        request,
        "finance/commission.html",
        {"comissao": comissao, "pagamentos": pagamentos, "estornos": estornos},
    )


# --- Bank statement (0.20.0) ------------------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def extratos(request):
    form = ImportarExtratoForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not pode(request, Modulo.FINANCEIRO, Acao.CRIAR):
            raise PermissionDenied
        if form.is_valid():
            arquivo = form.cleaned_data["arquivo"]
            try:
                importacao = reconciliation.importar(
                    form.cleaned_data["conta"],
                    nome_arquivo=arquivo.name,
                    conteudo=arquivo.read(),
                    user=request.user,
                )
            except ArquivoInvalido as erro:
                form.add_error("arquivo", str(erro))
            else:
                messages.success(
                    request,
                    _("Extrato importado: %(novas)s transações novas, %(repetidas)s já importadas.")
                    % {"novas": importacao.novas, "repetidas": importacao.repetidas},
                )
                if importacao.ignoradas:
                    messages.warning(
                        request,
                        ngettext(
                            "%(n)s linha do arquivo não tinha data ou valor legível e não foi "
                            "importada. Confira no extrato do banco.",
                            "%(n)s linhas do arquivo não tinham data ou valor legível e não "
                            "foram importadas. Confira no extrato do banco.",
                            importacao.ignoradas,
                        )
                        % {"n": importacao.ignoradas},
                    )
                outra = reconciliation.outra_conta_no_banco(importacao)
                if outra:
                    messages.warning(
                        request,
                        _(
                            "Atenção: este arquivo é da conta %(nova)s no banco, mas a anterior "
                            "importada em %(conta)s era da conta %(antiga)s."
                        )
                        % {
                            "nova": importacao.conta_no_banco,
                            "conta": importacao.conta,
                            "antiga": outra,
                        },
                    )
                return redirect("finance:statement", pk=importacao.pk)
    importacoes = StatementImport.objects.select_related("conta", "created_by")
    pendentes = dict(
        BankTransaction.objects.filter(situacao=BankTransaction.Situacao.PENDENTE)
        .values("importacao")
        .annotate(n=Count("pk"))
        .values_list("importacao", "n")
    )
    pagina = Paginator(importacoes, 30).get_page(request.GET.get("pagina"))
    for importacao in pagina:
        importacao.pendentes = pendentes.get(importacao.pk, 0)
    return render(request, "finance/statements.html", {"form": form, "pagina": pagina})


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def extrato(request, pk):
    importacao = get_object_or_404(StatementImport.objects.select_related("conta"), pk=pk)
    transacoes = list(
        importacao.transacoes.select_related(
            "pagamento__parcela__lancamento__patient", "movimento__caixa__conta"
        )
    )
    por_transacao = reconciliation.candidatos(transacoes)
    for transacao in transacoes:
        transacao.candidatos = por_transacao.get(transacao.pk, [])
    saldo_sistema = reconciliation.saldo_no_sistema(importacao)
    return render(
        request,
        "finance/statement.html",
        {
            "importacao": importacao,
            "transacoes": transacoes,
            "pendentes": sum(t.situacao == BankTransaction.Situacao.PENDENTE for t in transacoes),
            "unicos": sum(len(t.candidatos) == 1 for t in transacoes),
            "saldo_sistema": saldo_sistema,
            "diferenca": importacao.saldo - saldo_sistema if saldo_sistema is not None else None,
        },
    )


def _voltar_ao_extrato(transacao):
    return redirect(
        f"{reverse('finance:statement', args=[transacao.importacao_id])}#t{transacao.pk}"
    )


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def extrato_conciliar_unicos(request, pk):
    importacao = get_object_or_404(StatementImport.objects, pk=pk)
    feitas = reconciliation.conciliar_unicos(importacao, user=request.user)
    messages.success(request, _("%(n)s transações conciliadas.") % {"n": feitas})
    return redirect("finance:statement", pk=importacao.pk)


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def transacao_acao(request, pk, acao):
    transacao = get_object_or_404(BankTransaction.objects, pk=pk)
    try:
        if acao == "reconcile":
            reconciliation.conciliar(transacao, request.POST.get("chave", ""), user=request.user)
        elif acao == "ignore":
            motivo = request.POST.get("motivo", "").strip()[:200]
            if not motivo:
                raise ValidationError(_("Informe o motivo para ignorar a transação."))
            reconciliation.ignorar(transacao, motivo=motivo, user=request.user)
        else:
            reconciliation.desfazer(transacao)
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
    return _voltar_ao_extrato(transacao)


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def transacao_lancamento(request, pk):
    transacao = get_object_or_404(BankTransaction.objects.select_related("conta"), pk=pk)
    form = LancamentoDaTransacaoForm(
        request.POST or None,
        entrada=transacao.entrada,
        initial={"descricao": transacao.descricao},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reconciliation.criar_lancamento(transacao, user=request.user, **form.cleaned_data)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento criado e conciliado."))
        return _voltar_ao_extrato(transacao)
    return render(request, "finance/transaction_entry.html", {"form": form, "transacao": transacao})
