import datetime
import json

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.permissoes import Acao, Modulo, exige_permissao, pode
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from . import servicos
from .forms import AgendamentoForm, TipoAtendimentoForm
from .models import Agendamento, TipoAtendimento


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def tipos(request):
    return render(request, "agenda/tipos.html", {"tipos": TipoAtendimento.objects.all()})


@exige_permissao(Modulo.CADASTROS, Acao.CRIAR)
def tipo_novo(request):
    return _formulario(request, TipoAtendimento())


@exige_permissao(Modulo.CADASTROS, Acao.ALTERAR)
def tipo_editar(request, pk):
    return _formulario(request, get_object_or_404(TipoAtendimento.objects, pk=pk))


def _formulario(request, tipo):
    form = TipoAtendimentoForm(request.POST or None, instance=tipo, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Tipo de atendimento {tipo.nome} salvo.")
        return redirect("agenda:tipos")
    return render(request, "agenda/tipo_form.html", {"form": form, "tipo": tipo})


@exige_permissao(Modulo.CADASTROS, Acao.EXCLUIR)
def tipo_excluir(request, pk):
    tipo = get_object_or_404(TipoAtendimento.objects, pk=pk)
    if request.method == "POST":
        try:
            tipo.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{tipo.nome} já foi usado em agendamentos e não pode ser excluído. "
                "Desmarque “ativo” para escondê-lo.",
            )
        else:
            messages.success(request, f"Tipo de atendimento {tipo.nome} excluído.")
        return redirect("agenda:tipos")
    return render(request, "agenda/tipo_excluir.html", {"tipo": tipo})


# --- Schedule ----------------------------------------------------------------------

SESSAO_PROFISSIONAL = "agenda_profissional"


def _resposta_sucesso(mensagem):
    """Empty HTMX response that tells the page to close the modal and reload events."""
    resposta = HttpResponse(status=204)
    resposta["HX-Trigger"] = json.dumps({"agendaAtualizada": {"mensagem": mensagem}})
    return resposta


def _periodo(request):
    """The [start, end) range FullCalendar asks for, as aware datetimes."""
    try:
        inicio = datetime.datetime.fromisoformat(request.GET["start"])
        fim = datetime.datetime.fromisoformat(request.GET["end"])
    except (KeyError, ValueError):
        return None
    if timezone.is_naive(inicio):
        inicio, fim = timezone.make_aware(inicio), timezone.make_aware(fim)
    if fim <= inicio or fim - inicio > datetime.timedelta(days=62):
        return None
    return inicio, fim


@exige_permissao(Modulo.AGENDA, Acao.VER)
def calendario(request):
    profissionais = list(Profissional.objects.filter(ativo=True))
    escolhido = request.GET.get("profissional") or request.session.get(SESSAO_PROFISSIONAL)
    profissional = next(
        (p for p in profissionais if str(p.pk) == str(escolhido)),
        profissionais[0] if profissionais else None,
    )
    if profissional is not None:
        request.session[SESSAO_PROFISSIONAL] = profissional.pk
    clinica = request.clinica
    ver_rechamadas = pode(request, Modulo.RECHAMADAS, Acao.VER)
    configuracao = {
        "profissional": profissional.pk if profissional else None,
        "inicio": clinica.agenda_inicio.strftime("%H:%M:%S"),
        "fim": clinica.agenda_fim.strftime("%H:%M:%S"),
        "intervalo": clinica.agenda_intervalo,
        "data": request.GET.get("data") or "",
        "pode": {acao: pode(request, Modulo.AGENDA, acao) for acao in ("criar", "alterar")},
        "urls": {
            "eventos": reverse("agenda:eventos"),
            "novo": reverse("agenda:novo"),
            "aniversariantes": reverse("agenda:aniversariantes"),
            "aniversariantes_dia": reverse("agenda:aniversariantes_dia"),
            "rechamadas": reverse("rechamadas:resumo") if ver_rechamadas else None,
            "rechamadas_dia": reverse("rechamadas:do_dia") if ver_rechamadas else None,
        },
    }
    return render(
        request,
        "agenda/calendario.html",
        {
            "profissionais": profissionais,
            "profissional": profissional,
            "tipos": TipoAtendimento.objects.filter(ativo=True),
            "configuracao": configuracao,
        },
    )


@exige_permissao(Modulo.AGENDA, Acao.VER)
def eventos(request):
    periodo = _periodo(request)
    profissional = request.GET.get("profissional", "")
    if periodo is None or not profissional.isdigit():
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)
    inicio, fim = periodo
    agendamentos = Agendamento.objects.filter(
        profissional_id=int(profissional), inicio__lt=fim, fim__gt=inicio
    ).select_related("tipo", "paciente")
    return JsonResponse(
        [
            {
                "id": agendamento.pk,
                "title": agendamento.titulo,
                "start": timezone.localtime(agendamento.inicio).isoformat(),
                "end": timezone.localtime(agendamento.fim).isoformat(),
                "backgroundColor": agendamento.tipo.cor,
                "borderColor": agendamento.tipo.cor,
                "textColor": "#212529",
                "extendedProps": {
                    "tipo": agendamento.tipo.nome,
                    "descricao": agendamento.descricao,
                    "url": reverse("agenda:editar", args=[agendamento.pk]),
                },
            }
            for agendamento in agendamentos
        ],
        safe=False,
    )


@exige_permissao(Modulo.AGENDA, Acao.CRIAR)
def novo(request):
    inicial = {
        campo: request.GET[parametro]
        for campo, parametro in [
            ("profissional", "profissional"),
            ("data", "data"),
            ("hora_inicio", "inicio"),
            ("hora_fim", "fim"),
        ]
        if request.GET.get(parametro)
    }
    form = AgendamentoForm(
        request.POST or None, initial=inicial, instance=Agendamento(), clinica=request.clinica
    )
    if request.method == "POST" and form.is_valid():
        try:
            criados = servicos.criar(form.instance, form.intervalos, request.user)
        except IntegrityError:
            form.add_error(
                None, "Outro agendamento acabou de ocupar este horário. Nada foi gravado."
            )
        else:
            total = len(criados)
            return _resposta_sucesso(
                "Agendamento criado." if total == 1 else f"{total} agendamentos criados."
            )
    return render(request, "agenda/_form.html", {"form": form, "agendamento": form.instance})


@exige_permissao(Modulo.AGENDA, Acao.ALTERAR)
def editar(request, pk):
    agendamento = get_object_or_404(Agendamento.objects.select_related("paciente"), pk=pk)
    form = AgendamentoForm(request.POST or None, instance=agendamento, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(
                None, "Outro agendamento acabou de ocupar este horário. Nada foi gravado."
            )
        else:
            return _resposta_sucesso("Agendamento alterado.")
    return render(request, "agenda/_form.html", {"form": form, "agendamento": agendamento})


@exige_permissao(Modulo.AGENDA, Acao.EXCLUIR)
def excluir(request, pk):
    agendamento = get_object_or_404(Agendamento.objects.select_related("paciente"), pk=pk)
    if request.method == "POST":
        excluidos = Agendamento.objects.filter(pk=agendamento.pk)
        if request.POST.get("escopo") == "serie" and agendamento.serie:
            # This one and the following ones of the same series.
            excluidos = Agendamento.objects.filter(
                serie=agendamento.serie, inicio__gte=agendamento.inicio
            )
        total, _ = excluidos.delete()
        return _resposta_sucesso(
            "Agendamento excluído." if total == 1 else f"{total} agendamentos excluídos."
        )
    proximos = 0
    if agendamento.serie:
        proximos = Agendamento.objects.filter(
            serie=agendamento.serie, inicio__gt=agendamento.inicio
        ).count()
    return render(
        request, "agenda/_excluir.html", {"agendamento": agendamento, "proximos": proximos}
    )


def _aniversariantes_em(dias):
    """{date: [patients]} for active patients whose birthday falls on the given days."""
    filtro = Q()
    for dia in dias:
        filtro |= Q(data_nascimento__month=dia.month, data_nascimento__day=dia.day)
    resultado = {dia: [] for dia in dias}
    if not dias:
        return resultado
    pacientes = Paciente.objects.filter(filtro, ativo=True).order_by("nome")
    por_mes_dia = {(dia.month, dia.day): dia for dia in dias}
    for paciente in pacientes:
        nascimento = paciente.data_nascimento
        resultado[por_mes_dia[(nascimento.month, nascimento.day)]].append(paciente)
    return resultado


@exige_permissao(Modulo.AGENDA, Acao.VER)
def aniversariantes(request):
    """Number of birthdays per day in the period shown by the calendar."""
    periodo = _periodo(request)
    if periodo is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)
    inicio = timezone.localdate(periodo[0])
    total_dias = (timezone.localdate(periodo[1]) - inicio).days
    dias = [inicio + datetime.timedelta(days=n) for n in range(total_dias)]
    return JsonResponse(
        {dia.isoformat(): len(lista) for dia, lista in _aniversariantes_em(dias).items() if lista}
    )


@exige_permissao(Modulo.AGENDA, Acao.VER)
def aniversariantes_dia(request):
    try:
        dia = datetime.date.fromisoformat(request.GET.get("data", ""))
    except ValueError:
        return HttpResponse("Data inválida.", status=400)
    aniversariantes = [
        (paciente, dia.year - paciente.data_nascimento.year)
        for paciente in _aniversariantes_em([dia])[dia]
    ]
    return render(
        request, "agenda/_aniversariantes.html", {"dia": dia, "aniversariantes": aniversariantes}
    )
