from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.agenda.models import Agendamento
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import registrar
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from .forms import (
    AdendoForm,
    AnexoForm,
    AtendimentoForm,
    AtestadoForm,
    PedidoDeExamesForm,
    ReceitaForm,
)
from .models import CAMPOS_DA_ANAMNESE, Anexo, Atendimento, Atestado, PedidoDeExames, Receita
from .permissoes import acessa_prontuario, administra_prontuario, profissional_do_usuario

Acao = RegistroAuditoria.Acao
# The audit log names the changed fields but never copies clinical text (decision 081).
SIGILO = "(conteúdo clínico)"


def exige_profissional(view):
    """Only practitioners and the system administrator reach the medical record; the view
    gets the user's Profissional (None for a system administrator who is not one)."""

    @wraps(view)
    @login_required
    def protegida(request, *args, **kwargs):
        if not acessa_prontuario(request):
            raise PermissionDenied
        return view(request, profissional_do_usuario(request), *args, **kwargs)

    return protegida


def _auditar(acao, atendimento, campos):
    if campos:
        registrar(acao, atendimento, alteracoes={campo: [SIGILO, SIGILO] for campo in campos})


def _finalizar(request, atendimento):
    atendimento.finalizado_em = timezone.now()
    atendimento.finalizado_por = request.user
    atendimento.save(update_fields=["finalizado_em", "finalizado_por", "alterado_em"])
    registrar(Acao.ALTERAR, atendimento, alteracoes={"finalizado": [None, "sim"]})
    messages.success(
        request, _("Atendimento finalizado. A partir de agora, correções são feitas por adendo.")
    )


@exige_profissional
def novo(request, profissional, paciente):
    paciente = get_object_or_404(Paciente.objects, pk=paciente, arquivado=False)
    agendamento = None
    codigo = request.POST.get("agendamento") or request.GET.get("agendamento") or ""
    if codigo.isdecimal():
        agendamento = get_object_or_404(Agendamento.objects, pk=codigo, paciente=paciente)
        existente = Atendimento.objects.filter(agendamento=agendamento).first()
        if existente is not None:
            return redirect("prontuario:atendimento", pk=existente.pk)
    inicial = {"data": agendamento.inicio if agendamento else timezone.now()}
    profissionais = None
    if administra_prontuario(request):
        profissionais = Profissional.objects.filter(ativo=True)
        inicial["profissional"] = agendamento.profissional if agendamento else profissional
    form = AtendimentoForm(request.POST or None, initial=inicial, profissionais=profissionais)
    if request.method == "POST" and form.is_valid():
        atendimento = form.save(commit=False)
        atendimento.paciente = paciente
        atendimento.profissional = form.cleaned_data.get("profissional") or profissional
        atendimento.agendamento = agendamento
        atendimento.criado_por = request.user
        atendimento.save()
        _auditar(
            Acao.CRIAR, atendimento, [c for c in CAMPOS_DA_ANAMNESE if getattr(atendimento, c)]
        )
        if request.POST.get("acao") == "finalizar":
            _finalizar(request, atendimento)
        else:
            messages.success(request, _("Atendimento salvo."))
        return redirect("prontuario:atendimento", pk=atendimento.pk)
    return render(
        request,
        "prontuario/atendimento.html",
        {"form": form, "paciente": paciente, "agendamento": agendamento, "editavel": True},
    )


@exige_profissional
def atendimento(request, profissional, pk):
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente", "profissional", "agendamento"), pk=pk
    )
    # Only its author (or the system administrator) changes a visit, until it is finalized.
    administra = administra_prontuario(request)
    do_autor = profissional is not None and atendimento.profissional_id == profissional.pk
    editavel = not atendimento.finalizado and (do_autor or administra)
    form = AtendimentoForm(request.POST or None, instance=atendimento) if editavel else None
    if request.method == "POST":
        if not editavel:
            raise PermissionDenied
        if form.is_valid():
            alterados = list(form.changed_data)
            form.save()
            _auditar(Acao.ALTERAR, atendimento, alterados)
            if request.POST.get("acao") == "finalizar":
                _finalizar(request, atendimento)
            else:
                messages.success(request, _("Atendimento salvo."))
            return redirect("prontuario:atendimento", pk=atendimento.pk)
    else:
        registrar(Acao.VISUALIZAR, atendimento)
    return render(
        request,
        "prontuario/atendimento.html",
        {
            "atendimento": atendimento,
            "paciente": atendimento.paciente,
            "agendamento": atendimento.agendamento,
            "form": form,
            "editavel": editavel,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("profissional"),
            "adendo_form": AdendoForm() if atendimento.finalizado else None,
            # Certificates and prescriptions are issued by the visit's author (decision 082).
            "emite_documentos": do_autor or administra,
            "administra": administra,
            "atestados": atendimento.atestados.all(),
            "receitas": atendimento.receitas.all(),
            "pedidos": atendimento.pedidos_de_exames.all(),
            # Never the file contents in a list.
            "anexos": atendimento.anexos.defer("conteudo").select_related("profissional"),
            "anexo_form": AnexoForm(),
            "remove_anexos": not atendimento.finalizado,
        },
    )


def _campos(atendimento):
    return [
        (atendimento._meta.get_field(campo).verbose_name, getattr(atendimento, campo))
        for campo in CAMPOS_DA_ANAMNESE
    ]


def _do_autor(request, profissional, pk):
    """The visit, if the user is its author or the system administrator."""
    atendimento = get_object_or_404(Atendimento.objects.select_related("paciente"), pk=pk)
    do_autor = profissional is not None and atendimento.profissional_id == profissional.pk
    if not (do_autor or administra_prontuario(request)):
        raise PermissionDenied
    return atendimento


@exige_profissional
def imprimir(request, profissional, pk):
    """The finalized visit, ready to print and sign (without a digital signature, the
    printed and signed copy is the legal record)."""
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente", "profissional"), pk=pk
    )
    if not atendimento.finalizado:
        raise PermissionDenied
    registrar(Acao.VISUALIZAR, atendimento, descricao=f"{atendimento} (impressão)")
    return render(
        request,
        "prontuario/imprimir.html",
        {
            "atendimento": atendimento,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("profissional"),
        },
    )


@exige_profissional
def atestado_novo(request, profissional, pk):
    atendimento = _do_autor(request, profissional, pk)
    agendamento = atendimento.agendamento
    momento = timezone.localtime(agendamento.inicio if agendamento else atendimento.data)
    inicial = {
        "data": momento.date(),
        "hora_inicio": momento.time().replace(second=0, microsecond=0),
        "hora_fim": timezone.localtime(agendamento.fim).time() if agendamento else None,
    }
    form = AtestadoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        atestado = form.save(commit=False)
        atestado.atendimento = atendimento
        atestado.profissional = atendimento.profissional
        atestado.criado_por = request.user
        atestado.save()
        registrar(
            Acao.CRIAR,
            atestado,
            alteracoes={
                "tipo": [None, atestado.tipo],
                "dias": [None, atestado.dias],
                **({"observacao": [None, SIGILO]} if atestado.observacao else {}),
            },
        )
        messages.success(request, _("Atestado emitido."))
        return redirect("prontuario:atestado", pk=atestado.pk)
    return render(
        request,
        "prontuario/documento_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir atestado")},
    )


@exige_profissional
def receita_nova(request, profissional, pk):
    atendimento = _do_autor(request, profissional, pk)
    form = ReceitaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receita = form.save(commit=False)
        receita.atendimento = atendimento
        receita.profissional = atendimento.profissional
        receita.criado_por = request.user
        receita.save()
        registrar(Acao.CRIAR, receita, alteracoes={"prescricao": [None, SIGILO]})
        messages.success(request, _("Receita emitida."))
        return redirect("prontuario:receita", pk=receita.pk)
    return render(
        request,
        "prontuario/documento_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir receita")},
    )


@exige_profissional
def atestado(request, profissional, pk):
    atestado = get_object_or_404(
        Atestado.objects.select_related("atendimento__paciente", "profissional"), pk=pk
    )
    registrar(Acao.VISUALIZAR, atestado)
    return render(request, "prontuario/atestado.html", {"atestado": atestado})


@exige_profissional
def receita(request, profissional, pk):
    receita = get_object_or_404(
        Receita.objects.select_related("atendimento__paciente", "profissional"), pk=pk
    )
    registrar(Acao.VISUALIZAR, receita)
    linhas = [linha for linha in receita.prescricao.splitlines() if linha.strip()]
    return render(request, "prontuario/receita.html", {"receita": receita, "linhas": linhas})


@require_POST
@exige_profissional
def adendo(request, profissional, pk):
    atendimento = get_object_or_404(Atendimento.objects, pk=pk)
    if not atendimento.finalizado:
        raise PermissionDenied  # before finalizing, the author simply edits the visit
    form = AdendoForm(request.POST)
    if form.is_valid():
        adendo = form.save(commit=False)
        adendo.atendimento = atendimento
        adendo.profissional = profissional or atendimento.profissional
        adendo.criado_por = request.user
        adendo.save()
        registrar(Acao.CRIAR, adendo, alteracoes={"texto": [None, SIGILO]})
        messages.success(request, _("Adendo incluído."))
    else:
        messages.error(request, _("Escreva o adendo."))
    return redirect("prontuario:atendimento", pk=atendimento.pk)


@exige_profissional
def pedido_de_exames_novo(request, profissional, pk):
    atendimento = _do_autor(request, profissional, pk)
    form = PedidoDeExamesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pedido = form.save(commit=False)
        pedido.atendimento = atendimento
        pedido.profissional = atendimento.profissional
        pedido.criado_por = request.user
        pedido.save()
        registrar(
            Acao.CRIAR,
            pedido,
            alteracoes={
                "exames": [None, SIGILO],
                **({"indicacao": [None, SIGILO]} if pedido.indicacao else {}),
            },
        )
        messages.success(request, _("Pedido de exames emitido."))
        return redirect("prontuario:pedido_de_exames", pk=pedido.pk)
    return render(
        request,
        "prontuario/documento_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Pedir exames")},
    )


@exige_profissional
def pedido_de_exames(request, profissional, pk):
    pedido = get_object_or_404(
        PedidoDeExames.objects.select_related("atendimento__paciente", "profissional"), pk=pk
    )
    registrar(Acao.VISUALIZAR, pedido)
    linhas = [linha for linha in pedido.exames.splitlines() if linha.strip()]
    return render(request, "prontuario/pedido_de_exames.html", {"pedido": pedido, "linhas": linhas})


@require_POST
@exige_profissional
def anexo_enviar(request, profissional, pk):
    """Any practitioner adds files to a visit, even a finalized one (results arrive later)."""
    atendimento = get_object_or_404(Atendimento.objects, pk=pk)
    if request.user.demonstracao:
        messages.error(request, _("Contas de demonstração não enviam anexos."))
        return redirect("prontuario:atendimento", pk=atendimento.pk)
    form = AnexoForm(request.POST, request.FILES)
    if form.is_valid():
        arquivo = form.cleaned_data["arquivo"]
        anexo = Anexo.objects.create(
            atendimento=atendimento,
            descricao=form.cleaned_data["descricao"],
            nome=arquivo.name[:255],
            tipo=arquivo.tipo_conferido,
            tamanho=arquivo.size,
            conteudo=arquivo.read(),
            profissional=profissional or atendimento.profissional,
            criado_por=request.user,
        )
        registrar(
            Acao.CRIAR,
            anexo,
            descricao=f"{atendimento} – {_('anexo')}",
            alteracoes={"arquivo": [None, SIGILO]},
        )
        messages.success(request, _("Anexo incluído."))
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect("prontuario:atendimento", pk=atendimento.pk)


@exige_profissional
def anexo(request, profissional, pk):
    anexo = get_object_or_404(Anexo.objects.select_related("atendimento"), pk=pk)
    registrar(Acao.VISUALIZAR, anexo, descricao=f"{anexo.atendimento} – {_('anexo')}")
    resposta = HttpResponse(bytes(anexo.conteudo), content_type=anexo.tipo)
    # Opened in the browser (only PDF, JPG and PNG are ever stored), never cached.
    nome = "".join(c for c in anexo.nome if c.isalnum() or c in "._- ") or "anexo"
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_POST
@exige_profissional
def anexo_remover(request, profissional, pk):
    """Who sent a file (or the system administrator) removes it while the visit is still a
    draft; afterwards it stays."""
    anexo = get_object_or_404(Anexo.objects.select_related("atendimento").defer("conteudo"), pk=pk)
    quem_enviou = anexo.criado_por_id == request.user.pk
    if anexo.atendimento.finalizado or not (quem_enviou or administra_prontuario(request)):
        raise PermissionDenied
    atendimento = anexo.atendimento
    registrar(
        Acao.EXCLUIR,
        anexo,
        descricao=f"{atendimento} – {_('anexo')}",
        alteracoes={"arquivo": [SIGILO, None]},
    )
    anexo.delete()
    messages.success(request, _("Anexo removido."))
    return redirect("prontuario:atendimento", pk=atendimento.pk)
