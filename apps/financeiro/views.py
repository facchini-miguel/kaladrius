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

from apps.core.ordem import chave_alfabetica
from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.core.templatetags.formatos import moeda
from apps.core.validadores import normalizar_cnpj
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from . import comissoes, conciliacao, servicos
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
from .ofx import ArquivoInvalido

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
            centro_custo=dados.get("centro_custo"),
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
    form = LancamentoPagarForm(
        request.POST or None,
        clinica=request.clinica,
        initial={"fornecedor": request.GET.get("fornecedor")},
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        lancamento = servicos.criar_lancamento(
            clinica=request.clinica,
            tipo=Lancamento.Tipo.PAGAR,
            fornecedor=dados["fornecedor"],
            pessoa=dados["pessoa"].strip(),
            descricao=dados["descricao"],
            categoria=dados["categoria"],
            centro_custo=dados.get("centro_custo"),
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
        Lancamento.objects.select_related("paciente", "categoria", "centro_custo", "profissional"),
        pk=pk,
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
            "comissao": Comissao.objects.filter(lancamento=lancamento).first(),
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
        try:
            servicos.estornar(pagamento, motivo=form.cleaned_data["motivo"], usuario=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Pagamento estornado."))
        return redirect("financeiro:lancamento", pk=pagamento.parcela.lancamento_id)
    return render(
        request,
        "financeiro/motivo.html",
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
    linhas = servicos.devedores()
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
        "financeiro/devedores.html",
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
    contas = list(Conta.objects.filter(tipo=Conta.Tipo.DINHEIRO, ativa=True))
    escolhida = request.GET.get("conta", "")
    conta = next((c for c in contas if str(c.pk) == escolhida), contas[0] if contas else None)
    if conta is not None:
        aberto = servicos.caixa_aberto(conta)
        if aberto is not None:
            return redirect("financeiro:caixa_detalhe", pk=aberto.pk)
    saldo = dict(servicos.saldos_das_contas()).get(conta) if conta else None
    # Empty on purpose: the opening amount is what is counted, not the system balance.
    form = AbrirCaixaForm(request.POST or None)
    if request.method == "POST" and conta is not None:
        if not pode(request, Modulo.RECEBIMENTOS, Acao.CRIAR):
            raise PermissionDenied
        if form.is_valid():
            try:
                novo = servicos.abrir_caixa(
                    conta, valor=form.cleaned_data["valor"], usuario=request.user
                )
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
                return redirect(f"{request.path}?conta={conta.pk}")
            messages.success(request, _("Caixa aberto."))
            return redirect("financeiro:caixa_detalhe", pk=novo.pk)
    historico = Caixa.objects.filter(conta=conta).select_related("aberto_por", "fechado_por")[:30]
    return render(
        request,
        "financeiro/caixa.html",
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
        Caixa.objects.select_related("conta", "aberto_por", "fechado_por"), pk=pk
    )
    return render(
        request,
        "financeiro/caixa_detalhe.html",
        {"caixa": sessao, "resumo": servicos.resumo_do_caixa(sessao)},
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_movimento(request, pk, tipo):
    sessao = get_object_or_404(Caixa.objects.select_related("conta"), pk=pk, fechado_em=None)
    if tipo not in MovimentoCaixa.Tipo.values:
        raise Http404
    form = MovimentoCaixaForm(request.POST or None, caixa=sessao)
    if request.method == "POST" and form.is_valid():
        try:
            servicos.movimentar_caixa(sessao, tipo=tipo, usuario=request.user, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Movimento registrado."))
            return redirect("financeiro:caixa_detalhe", pk=sessao.pk)
    return render(
        request,
        "financeiro/caixa_form.html",
        {"caixa": sessao, "form": form, "titulo": MovimentoCaixa.Tipo(tipo).label},
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_fechar(request, pk):
    sessao = get_object_or_404(Caixa.objects.select_related("conta"), pk=pk, fechado_em=None)
    form = FecharCaixaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        servicos.fechar_caixa(sessao, usuario=request.user, **form.cleaned_data)
        messages.success(request, _("Caixa fechado."))
        return redirect("financeiro:caixa_detalhe", pk=sessao.pk)
    return render(
        request,
        "financeiro/caixa_form.html",
        {
            "caixa": sessao,
            "form": form,
            "titulo": _("Fechar caixa"),
            "esperado": servicos.resumo_do_caixa(sessao)["esperado"],
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
        {
            "de": de,
            "ate": ate,
            "relatorio": servicos.relatorio(de, ate),
            "fechado_ate": servicos.fechado_ate(request.clinica.pk),
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
    grupos = servicos.ligar_grupos(GrupoContabil.objects.filter(ativo=True))
    metas = dict(Planejamento.objects.filter(ano=ano).values_list("grupo_id", "valor"))
    form = PlanejamentoForm(request.POST or None, grupos=grupos, metas=metas)
    if request.method == "POST":
        if not pode_alterar:
            raise PermissionDenied
        if request.POST.get("acao") == "copiar":
            copiadas = servicos.copiar_metas(ano)
            messages.success(
                request,
                ngettext(
                    "%(n)s meta copiada do ano anterior.",
                    "%(n)s metas copiadas do ano anterior.",
                    copiadas,
                )
                % {"n": copiadas},
            )
            return redirect(f"{reverse('financeiro:planejamento')}?ano={ano}")
        if form.is_valid():
            servicos.salvar_metas(ano, form.valores())
            messages.success(request, _("Planejamento salvo."))
            return redirect(f"{reverse('financeiro:planejamento')}?ano={ano}")
    dados = servicos.planejamento(ano)
    for secao in dados["secoes"]:
        for linha in secao["linhas"]:
            if pode_alterar and linha["grupo"].ativo:
                linha["campo"] = form[PlanejamentoForm.nome(linha["grupo"])]
    return render(
        request,
        "financeiro/planejamento.html",
        {
            **dados,
            "form": form,
            "pode_alterar": pode_alterar,
            "ano_anterior": ano - 1,
            "proximo_ano": ano + 1,
            "tem_metas_anteriores": Planejamento.objects.filter(ano=ano - 1).exists(),
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
                    servicos.fechar(request.clinica, dados["ate"], usuario=request.user)
                    messages.success(request, _("Financeiro fechado."))
                else:
                    servicos.reabrir(
                        request.clinica, dados["ate"], motivo=dados["motivo"], usuario=request.user
                    )
                    messages.success(request, _("Período reaberto."))
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
        return redirect("financeiro:fechamento")
    return render(
        request,
        "financeiro/fechamento.html",
        {
            "fechado_ate": servicos.fechado_ate(request.clinica.pk),
            "historico": Fechamento.objects.select_related("criado_por")[:30],
            "fechar_form": FecharForm() if pode_fechar else None,
            "reabrir_form": ReabrirForm() if pode_reabrir else None,
        },
    )


# --- Accounts, categories and cost centers (administrators) ----------------------------


CADASTROS = {
    "categorias": (Categoria, CategoriaForm),
    "contas": (Conta, ContaForm),
    "centros-de-custo": (CentroCusto, CentroCustoForm),
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


# --- Chart of accounts (decision 097) ---------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def plano_contas(request):
    """The chart of accounts as a tree: groups, subgroups and their categories."""
    grupos = servicos.ligar_grupos(GrupoContabil.objects.all())
    categorias = list(Categoria.objects.all())
    arvores = []
    for tipo, rotulo in Categoria.Tipo.choices:
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
    return render(request, "financeiro/plano_contas.html", {"arvores": arvores})


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def grupo_novo(request):
    return _grupo_form(request, GrupoContabil(tipo=request.GET.get("tipo") or None))


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def grupo_editar(request, pk):
    return _grupo_form(request, get_object_or_404(GrupoContabil.objects, pk=pk))


def _grupo_form(request, instancia):
    form = GrupoContabilForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        grupo = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": grupo.nome})
        return redirect("financeiro:plano_contas")
    return render(request, "financeiro/grupo_form.html", {"form": form, "instancia": instancia})


# --- Suppliers (decision 093) ---------------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fornecedores(request):
    busca = request.GET.get("q", "").strip()
    lista = Fornecedor.objects.all()
    if busca:
        filtro = Q(nome__unaccent__icontains=busca) | Q(razao_social__unaccent__icontains=busca)
        documento = normalizar_cnpj(busca)
        if any(c.isdigit() for c in documento):
            filtro |= Q(cpf_cnpj__startswith=documento)
        lista = lista.filter(filtro)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "financeiro/fornecedores.html",
        {"pagina": pagina, "busca": busca, "parametros": urlencode({"q": busca})},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fornecedor(request, pk):
    fornecedor = get_object_or_404(Fornecedor.objects, pk=pk)
    hoje = timezone.localdate()
    parcelas = list(
        Parcela.objects.com_saldo()
        .filter(lancamento__fornecedor=fornecedor)
        .select_related("lancamento")
        .order_by("-vencimento", "-pk")[:POR_PAGINA]
    )
    for parcela in parcelas:
        parcela.situacao = servicos.situacao(parcela, hoje)
    em_aberto = sum(
        (p.saldo for p in Parcela.objects.abertas().filter(lancamento__fornecedor=fornecedor)),
        start=ZERO,
    )
    return render(
        request,
        "financeiro/fornecedor.html",
        {"fornecedor": fornecedor, "parcelas": parcelas, "em_aberto": em_aberto},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def fornecedor_novo(request):
    return _fornecedor_form(request, Fornecedor())


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def fornecedor_editar(request, pk):
    return _fornecedor_form(request, get_object_or_404(Fornecedor.objects, pk=pk))


def _fornecedor_form(request, instancia):
    form = FornecedorForm(request.POST or None, instance=instancia, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        fornecedor = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": fornecedor.nome})
        return redirect("financeiro:fornecedor", pk=fornecedor.pk)
    return render(
        request, "financeiro/fornecedor_form.html", {"form": form, "instancia": instancia}
    )


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
        "financeiro/comissoes.html",
        {
            "ate": ate,
            "linhas": comissoes.resumo(ate),
            "sem_percentual": Profissional.objects.filter(ativo=True, comissao_percentual=0),
            "historico": Comissao.objects.select_related("profissional", "lancamento")[:30],
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def comissao_percentual(request, pk):
    profissional = get_object_or_404(Profissional.objects, pk=pk)
    form = PercentualComissaoForm(request.POST or None, instance=profissional)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Percentual de %(nome)s salvo.") % {"nome": profissional.nome})
        return redirect("financeiro:comissoes")
    return render(
        request,
        "financeiro/comissao_percentual.html",
        {"form": form, "profissional": profissional},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def comissao_pagar(request, pk):
    profissional = get_object_or_404(Profissional.objects, pk=pk)
    ate = _ate(request)
    padrao = (
        Categoria.objects.filter(tipo=Categoria.Tipo.DESPESA, nome="Comissões", ativa=True).first()
        or Categoria.objects.filter(tipo=Categoria.Tipo.DESPESA, ativa=True).first()
    )
    form = PagarComissaoForm(request.POST or None, initial={"categoria": padrao})
    if request.method == "POST" and form.is_valid():
        try:
            comissao = comissoes.pagar(
                profissional, ate=ate, usuario=request.user, **form.cleaned_data
            )
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
            return redirect(f"{reverse('financeiro:comissoes')}?ate={ate.isoformat()}")
        messages.success(request, _("Comissão lançada em A pagar."))
        return redirect("financeiro:lancamento", pk=comissao.lancamento_id)
    return render(
        request,
        "financeiro/comissao_pagar.html",
        {"form": form, "calculo": comissoes.pendente(profissional, ate), "ate": ate},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def comissao(request, pk):
    comissao = get_object_or_404(
        Comissao.objects.select_related("profissional", "lancamento"), pk=pk
    )
    pagamentos = comissao.pagamentos.select_related("parcela__lancamento__paciente").order_by(
        "data", "pk"
    )
    estornos = comissao.pagamentos_estornados.select_related(
        "parcela__lancamento__paciente", "comissao"
    ).order_by("data", "pk")
    for estorno in estornos:
        estorno.comissao_devolvida = comissoes.percentual_de(
            estorno.valor, estorno.comissao.percentual
        )
    return render(
        request,
        "financeiro/comissao.html",
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
                importacao = conciliacao.importar(
                    form.cleaned_data["conta"],
                    nome_arquivo=arquivo.name,
                    conteudo=arquivo.read(),
                    usuario=request.user,
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
                outra = conciliacao.outra_conta_no_banco(importacao)
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
                return redirect("financeiro:extrato", pk=importacao.pk)
    importacoes = ImportacaoExtrato.objects.select_related("conta", "criado_por")
    pendentes = dict(
        TransacaoBancaria.objects.filter(situacao=TransacaoBancaria.Situacao.PENDENTE)
        .values("importacao")
        .annotate(n=Count("pk"))
        .values_list("importacao", "n")
    )
    pagina = Paginator(importacoes, 30).get_page(request.GET.get("pagina"))
    for importacao in pagina:
        importacao.pendentes = pendentes.get(importacao.pk, 0)
    return render(request, "financeiro/extratos.html", {"form": form, "pagina": pagina})


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def extrato(request, pk):
    importacao = get_object_or_404(ImportacaoExtrato.objects.select_related("conta"), pk=pk)
    transacoes = list(
        importacao.transacoes.select_related(
            "pagamento__parcela__lancamento__paciente", "movimento__caixa__conta"
        )
    )
    por_transacao = conciliacao.candidatos(transacoes)
    for transacao in transacoes:
        transacao.candidatos = por_transacao.get(transacao.pk, [])
    saldo_sistema = conciliacao.saldo_no_sistema(importacao)
    return render(
        request,
        "financeiro/extrato.html",
        {
            "importacao": importacao,
            "transacoes": transacoes,
            "pendentes": sum(t.situacao == TransacaoBancaria.Situacao.PENDENTE for t in transacoes),
            "unicos": sum(len(t.candidatos) == 1 for t in transacoes),
            "saldo_sistema": saldo_sistema,
            "diferenca": importacao.saldo - saldo_sistema if saldo_sistema is not None else None,
        },
    )


def _voltar_ao_extrato(transacao):
    return redirect(
        f"{reverse('financeiro:extrato', args=[transacao.importacao_id])}#t{transacao.pk}"
    )


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def extrato_conciliar_unicos(request, pk):
    importacao = get_object_or_404(ImportacaoExtrato.objects, pk=pk)
    feitas = conciliacao.conciliar_unicos(importacao, usuario=request.user)
    messages.success(request, _("%(n)s transações conciliadas.") % {"n": feitas})
    return redirect("financeiro:extrato", pk=importacao.pk)


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def transacao_acao(request, pk, acao):
    transacao = get_object_or_404(TransacaoBancaria.objects, pk=pk)
    try:
        if acao == "conciliar":
            conciliacao.conciliar(transacao, request.POST.get("chave", ""), usuario=request.user)
        elif acao == "ignorar":
            motivo = request.POST.get("motivo", "").strip()[:200]
            if not motivo:
                raise ValidationError(_("Informe o motivo para ignorar a transação."))
            conciliacao.ignorar(transacao, motivo=motivo, usuario=request.user)
        else:
            conciliacao.desfazer(transacao)
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
    return _voltar_ao_extrato(transacao)


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def transacao_lancamento(request, pk):
    transacao = get_object_or_404(TransacaoBancaria.objects.select_related("conta"), pk=pk)
    form = LancamentoDaTransacaoForm(
        request.POST or None,
        entrada=transacao.entrada,
        initial={"descricao": transacao.descricao},
    )
    if request.method == "POST" and form.is_valid():
        try:
            conciliacao.criar_lancamento(transacao, usuario=request.user, **form.cleaned_data)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento criado e conciliado."))
        return _voltar_ao_extrato(transacao)
    return render(
        request, "financeiro/transacao_lancamento.html", {"form": form, "transacao": transacao}
    )
