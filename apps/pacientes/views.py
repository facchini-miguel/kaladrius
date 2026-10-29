from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from apps.agenda.models import Agendamento
from apps.agenda.servicos import agendamentos_visiveis
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import anonimizar, registrar
from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.core.validadores import normalizar_cnpj
from apps.financeiro.models import Lancamento, Pagamento, Parcela
from apps.financeiro.servicos import resumo_do_paciente
from apps.orcamentos.models import ItemOrcamento, Orcamento
from apps.prontuario.models import Atendimento
from apps.prontuario.permissoes import profissional_do_usuario
from apps.rechamadas.models import Rechamada

from .forms import PacienteForm
from .models import Paciente

POR_PAGINA = 50
SITUACOES = {
    "ativos": Q(ativo=True, arquivado=False),
    "inativos": Q(ativo=False, arquivado=False),
    "todos": Q(arquivado=False),
    "arquivados": Q(arquivado=True),  # clinic administrators only (see lista)
}


def _ve_arquivados(request):
    """Archived patients are seen (and restored or deleted) only by who could delete."""
    return pode(request, Modulo.PACIENTES, Acao.EXCLUIR)


def _visiveis(request):
    if _ve_arquivados(request):
        return Paciente.objects.all()
    return Paciente.objects.filter(arquivado=False)


def filtrar(pacientes, busca, tipo, situacao):
    """Search by name/company name (accent-insensitive), CPF/CNPJ prefix or patient code."""
    if busca:
        filtro = Q(nome__unaccent__icontains=busca) | Q(razao_social__unaccent__icontains=busca)
        documento = normalizar_cnpj(busca)
        if len(documento) >= 3 and not any(c.isspace() for c in busca.strip()):
            filtro |= Q(cpf_cnpj__startswith=documento)
        if busca.isdecimal() and len(busca) <= 9:
            filtro |= Q(pk=int(busca))
        pacientes = pacientes.filter(filtro)
    if tipo in Paciente.Tipo.values:
        pacientes = pacientes.filter(tipo=tipo)
    return pacientes.filter(SITUACOES.get(situacao, SITUACOES["ativos"]))


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def lista(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "")
    situacao = request.GET.get("situacao", "ativos")
    if situacao == "arquivados" and not _ve_arquivados(request):
        situacao = "ativos"
    pacientes = filtrar(Paciente.objects.select_related("cidade__uf"), busca, tipo, situacao)
    pagina = Paginator(pacientes, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "pacientes/lista.html",
        {
            "pagina": pagina,
            "busca": busca,
            "tipo": tipo,
            "situacao": situacao,
            "tipos": Paciente.Tipo.choices,
            "parametros": urlencode({"q": busca, "tipo": tipo, "situacao": situacao}),
        },
    )


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def ficha(request, pk):
    paciente = get_object_or_404(
        _visiveis(request).select_related("cidade__uf", "estado_civil", "arquivado_por"), pk=pk
    )
    # LGPD: access to a patient's record (health data) is logged.
    registrar(RegistroAuditoria.Acao.VISUALIZAR, paciente)
    rechamadas = Rechamada.objects.filter(paciente=paciente).order_by("-data")[:20]
    contexto = {"paciente": paciente, "rechamadas": rechamadas}
    if pode(request, Modulo.AGENDA, Acao.VER):
        contexto["agendamentos"] = _historico(request, paciente)
    if pode(request, Modulo.RECEBIMENTOS, Acao.VER):
        contexto["financeiro"] = resumo_do_paciente(paciente)
    if pode(request, Modulo.ORCAMENTOS, Acao.VER):
        contexto["orcamentos"] = list(
            Orcamento.objects.filter(paciente=paciente).prefetch_related("itens")[:10]
        )
    if profissional_do_usuario(request) is not None:
        contexto["prontuario"] = list(
            Atendimento.objects.filter(paciente=paciente).select_related("profissional")
        )
    return render(request, "pacientes/ficha.html", contexto)


HISTORICO = 10  # appointments shown in each list of the patient record


def _historico(request, paciente):
    """The patient's next and latest appointments (practitioners: only their own)."""
    deste = (
        agendamentos_visiveis(request)
        .filter(paciente=paciente)
        .select_related("profissional", "tipo")
    )
    agora = timezone.now()
    return {
        "proximos": list(deste.filter(fim__gt=agora).order_by("inicio")[:HISTORICO]),
        "anteriores": list(deste.filter(fim__lte=agora).order_by("-inicio")[:HISTORICO]),
        "total": deste.count(),
    }


@exige_permissao(Modulo.PACIENTES, Acao.CRIAR)
def novo(request):
    return _formulario(request, Paciente())


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def editar(request, pk):
    # An archived patient is restored before being changed.
    return _formulario(request, get_object_or_404(Paciente.objects, pk=pk, arquivado=False))


def _formulario(request, paciente):
    form = PacienteForm(request.POST or None, instance=paciente, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        paciente = form.save()
        messages.success(request, _("Paciente %(nome)s salvo.") % {"nome": paciente.nome})
        return redirect("pacientes:ficha", pk=paciente.pk)
    return render(request, "pacientes/form.html", {"form": form, "paciente": paciente})


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def arquivar(request, pk):
    paciente = get_object_or_404(Paciente.objects, pk=pk, arquivado=False)
    # Not while the patient still owes or is owed money: the administrator first receives or
    # cancels those entries (0.27.2, decision 075), so finance never lists archived patients.
    abertas = list(
        Parcela.objects.abertas()
        .filter(lancamento__paciente=paciente)
        .select_related("lancamento")
        .order_by("vencimento", "pk")
    )
    if abertas:
        if request.method == "POST":
            messages.error(
                request, _("Resolva as contas em aberto do paciente antes de arquivá-lo.")
            )
        return render(
            request, "pacientes/arquivar.html", {"paciente": paciente, "abertas": abertas}
        )
    if request.method == "POST":
        paciente.arquivado = True
        paciente.arquivado_em = timezone.now()
        paciente.arquivado_por = request.user
        paciente.save()
        messages.success(
            request,
            _(
                "Paciente %(nome)s arquivado. O histórico continua guardado e ele pode ser "
                "restaurado na lista de pacientes, em Situação: Arquivados."
            )
            % {"nome": paciente.nome},
        )
        return redirect("pacientes:lista")
    return render(request, "pacientes/arquivar.html", {"paciente": paciente})


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def restaurar(request, pk):
    paciente = get_object_or_404(Paciente.objects, pk=pk, arquivado=True)
    if request.method == "POST":
        paciente.arquivado = False
        paciente.arquivado_em = paciente.arquivado_por = None
        paciente.save()
        messages.success(request, _("Paciente %(nome)s restaurado.") % {"nome": paciente.nome})
    return redirect("pacientes:ficha", pk=paciente.pk)


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def excluir(request, pk):
    """Permanent deletion, only for an archived patient who asked for it (LGPD, art. 18).

    The appointments stay in the schedule without the patient (and without their notes),
    the recalls go, financial entries are kept (accounting history) without the patient
    and the notes, and the patient's personal data is removed from the audit log as well.
    """
    paciente = get_object_or_404(Paciente.objects, pk=pk, arquivado=True)
    # The medical record is kept for 20 years (Law 13.787/2018, decision 081): a patient
    # with one stays archived and is never permanently deleted.
    atendimentos = Atendimento.objects.filter(paciente=paciente).count()
    if atendimentos:
        if request.method == "POST":
            messages.error(request, _("Paciente com prontuário não pode ser excluído."))
        return render(
            request, "pacientes/excluir.html", {"paciente": paciente, "atendimentos": atendimentos}
        )
    if request.method == "POST":
        codigo = paciente.pk
        agendamentos = Agendamento.objects.filter(paciente=paciente)
        ids_agendamentos = list(agendamentos.values_list("pk", flat=True))
        rechamadas = Rechamada.objects.filter(paciente=paciente)
        ids_rechamadas = list(rechamadas.values_list("pk", flat=True))
        lancamentos = Lancamento.objects.filter(paciente=paciente)
        ids_lancamentos = list(lancamentos.values_list("pk", flat=True))
        ids_parcelas = list(
            Parcela.objects.filter(lancamento__in=ids_lancamentos).values_list("pk", flat=True)
        )
        ids_pagamentos = list(
            Pagamento.objects.filter(parcela__in=ids_parcelas).values_list("pk", flat=True)
        )
        orcamentos = Orcamento.objects.filter(paciente=paciente)
        ids_orcamentos = list(orcamentos.values_list("pk", flat=True))
        ids_itens = list(
            ItemOrcamento.objects.filter(orcamento__in=ids_orcamentos).values_list("pk", flat=True)
        )
        # Stored in Portuguese, like the rest of the data. Free-text notes may hold
        # personal data, so they go too; the amounts and dates stay (accounting history).
        excluido = f"Paciente excluído (código {codigo})"
        with transaction.atomic():
            orcamentos.delete()  # items go with them (cascade)
            agendamentos.update(paciente=None, descricao=excluido)
            lancamentos.update(paciente=None, pessoa=excluido, observacoes="")
            Pagamento.objects.filter(pk__in=ids_pagamentos).update(observacao="")
            rechamadas.delete()
            paciente.delete()
            anonimizar(Paciente, [codigo])
            anonimizar(Agendamento, ids_agendamentos)
            anonimizar(Rechamada, ids_rechamadas)
            anonimizar(Lancamento, ids_lancamentos)
            anonimizar(Parcela, ids_parcelas)
            anonimizar(Pagamento, ids_pagamentos)
            anonimizar(Orcamento, ids_orcamentos)
            anonimizar(ItemOrcamento, ids_itens)
            registrar(
                RegistroAuditoria.Acao.EXCLUIR,
                descricao=f"Paciente {codigo}: dados pessoais excluídos a pedido do titular",
            )
        messages.success(
            request,
            _("Os dados do paciente de código %(codigo)s foram excluídos.") % {"codigo": codigo},
        )
        return redirect(f"{reverse('pacientes:lista')}?situacao=arquivados")
    return render(request, "pacientes/excluir.html", {"paciente": paciente})


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def sugestoes(request):
    """Up to 10 active patients matching the text, for search-as-you-type fields (HTMX)."""
    busca = request.GET.get("q", "").strip()
    pacientes = filtrar(Paciente.objects.all(), busca, "", "ativos")[:10] if len(busca) >= 2 else []
    return render(request, "pacientes/_sugestoes.html", {"pacientes": pacientes})


MESES = [MONTHS[n] for n in range(1, 13)]  # translated month names (Django)


@exige_permissao(Modulo.ANIVERSARIANTES, Acao.VER)
def aniversariantes(request):
    hoje = timezone.localdate()
    mes = request.GET.get("mes", "")
    mes = int(mes) if mes.isdecimal() and 1 <= int(mes) <= 12 else hoje.month
    pacientes = Paciente.objects.filter(
        ativo=True, arquivado=False, data_nascimento__month=mes
    ).order_by("data_nascimento__day", "nome")
    ano = hoje.year if mes >= hoje.month else hoje.year + 1  # next birthday's year
    linhas = [(paciente, ano - paciente.data_nascimento.year) for paciente in pacientes]
    return render(
        request,
        "pacientes/aniversariantes.html",
        {"mes": mes, "meses": list(enumerate(MESES, start=1)), "linhas": linhas, "hoje": hoje},
    )
