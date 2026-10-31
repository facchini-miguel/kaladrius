"""Login, two-step verification and password recovery (decision 111)."""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, user_login_failed
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import registrar

from . import servicos
from .forms import CodigoForm, DesativarForm, EntrarForm, NovaSenhaForm, RecuperarSenhaForm

PENDENTE = "duas_etapas_pendente"
VALIDADE_PENDENTE = 5 * 60  # seconds to type the code after the password
TENTATIVAS_CODIGO = 5


class EntrarView(auth_views.LoginView):
    authentication_form = EntrarForm

    def form_valid(self, form):
        usuario = form.get_user()
        if not servicos.ativa_para(usuario):
            return super().form_valid(form)
        # Password right: the code from the app comes next, before the session is opened.
        self.request.session[PENDENTE] = {
            "usuario": usuario.pk,
            "backend": usuario.backend,
            "momento": time.time(),
            "tentativas": 0,
            "proximo": self.get_success_url(),
        }
        return redirect("conta:codigo")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        erros = contexto["form"].non_field_errors().as_data()
        return {
            **contexto,
            "endereco_bloqueado": any(e.code == "endereco_bloqueado" for e in erros),
            "recuperar_por_email": settings.RECUPERAR_SENHA_POR_EMAIL,
            "inatividade": self.request.GET.get("inatividade") == "1",
            "minutos": settings.INATIVIDADE_MINUTOS,
        }


def codigo(request):
    """Second step of the login: the 6-digit code of the app or a recovery code."""
    pendente = request.session.get(PENDENTE)
    if not pendente or time.time() - pendente["momento"] > VALIDADE_PENDENTE:
        request.session.pop(PENDENTE, None)
        messages.info(request, _("Entre de novo com o usuário e a senha."))
        return redirect("login")
    usuario = get_user_model().objects.get(pk=pendente["usuario"])
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if servicos.verificar(usuario, form.cleaned_data["codigo"]):
            del request.session[PENDENTE]
            login(request, usuario, backend=pendente["backend"])
            return redirect(pendente["proximo"])
        # Counted by the login protection too, so codes cannot be tried without end.
        user_login_failed.send(
            sender=__name__, credentials={"username": usuario.get_username()}, request=request
        )
        pendente["tentativas"] += 1
        if pendente["tentativas"] >= TENTATIVAS_CODIGO:
            del request.session[PENDENTE]
            messages.error(request, _("Muitos códigos errados. Entre de novo."))
            return redirect("login")
        request.session[PENDENTE] = pendente
        form.add_error("codigo", _("Código incorreto."))
    return render(request, "conta/codigo.html", {"form": form})


@login_required
@require_GET
def ativo(request):
    """Called by the page while the person is using it, so 30 idle minutes are counted only
    when nobody touches the computer (the session is renewed on every request)."""
    return HttpResponse(status=204)


@login_required
def duas_etapas(request):
    """Turn two-step verification on (QR code) or off, and make new recovery codes."""
    # The real row, not the request's lazy user: the audit log needs its model.
    usuario = get_user_model().objects.get(pk=request.user.pk)
    if usuario.demonstracao:
        messages.info(request, _("Contas de demonstração não usam verificação em duas etapas."))
        return redirect("inicio")
    acao = request.POST.get("acao")
    obrigatoria = servicos.obrigatoria(request)
    if servicos.ativa_para(usuario):
        # Required by the clinic: it can only be renewed (new codes), not turned off.
        desativar = (
            None
            if obrigatoria
            else DesativarForm(
                request.POST if acao == "desativar" else None, usuario=usuario, prefix="desativar"
            )
        )
        novos = CodigoForm(request.POST if acao == "codigos" else None, prefix="codigos")
        if acao == "desativar" and desativar is not None and desativar.is_valid():
            servicos.desativar(usuario)
            registrar(
                RegistroAuditoria.Acao.ALTERAR,
                usuario,
                descricao=f"{usuario}: verificação em duas etapas desativada",
            )
            messages.success(request, _("Verificação em duas etapas desativada."))
            return redirect("conta:duas_etapas")
        if acao == "codigos" and novos.is_valid():
            if servicos.verificar(usuario, novos.cleaned_data["codigo"]):
                return render(
                    request,
                    "conta/codigos.html",
                    {"codigos": servicos.novos_codigos(usuario)},
                )
            novos.add_error("codigo", _("Código incorreto."))
        restantes = usuario.codigos_recuperacao.filter(usado_em__isnull=True).count()
        return render(
            request,
            "conta/duas_etapas.html",
            {
                "ativa": True,
                "desativar": desativar,
                "novos": novos,
                "restantes": restantes,
                "obrigatoria": obrigatoria,
            },
        )
    dispositivo = servicos.preparar(usuario, novo=request.GET.get("novo") == "1")
    form = CodigoForm(request.POST if acao == "ativar" else None)
    if acao == "ativar" and form.is_valid():
        if servicos.verificar_app(dispositivo, form.cleaned_data["codigo"]):
            codigos = servicos.ativar(dispositivo)
            registrar(
                RegistroAuditoria.Acao.ALTERAR,
                usuario,
                descricao=f"{usuario}: verificação em duas etapas ativada",
            )
            return render(request, "conta/codigos.html", {"codigos": codigos, "ativada": True})
        form.add_error("codigo", _("Código incorreto. Confira a hora do celular e tente de novo."))
    endereco = servicos.endereco_do_app(dispositivo)
    return render(
        request,
        "conta/duas_etapas.html",
        {
            "ativa": False,
            "obrigatoria": obrigatoria,
            "form": form,
            "qr": servicos.qr_svg(endereco),
            "segredo": servicos.segredo_em_grupos(dispositivo.segredo),
        },
    )


def _com_email(view):
    """Password recovery only exists where the installation can send e-mail."""

    def protegida(request, *args, **kwargs):
        if not settings.RECUPERAR_SENHA_POR_EMAIL:
            raise Http404
        return view(request, *args, **kwargs)

    return protegida


recuperar = _com_email(
    auth_views.PasswordResetView.as_view(
        form_class=RecuperarSenhaForm,
        template_name="conta/recuperar.html",
        email_template_name="conta/email_recuperar.txt",
        subject_template_name="conta/email_recuperar_assunto.txt",
        extra_email_context={"nome_sistema": settings.NOME_SISTEMA},
        success_url=reverse_lazy("conta:recuperar_enviado"),
    )
)
recuperar_enviado = _com_email(
    auth_views.PasswordResetDoneView.as_view(template_name="conta/recuperar_enviado.html")
)
nova_senha = _com_email(
    auth_views.PasswordResetConfirmView.as_view(
        form_class=NovaSenhaForm,
        template_name="conta/nova_senha.html",
        success_url=reverse_lazy("conta:senha_redefinida"),
    )
)
senha_redefinida = _com_email(
    auth_views.PasswordResetCompleteView.as_view(template_name="conta/senha_redefinida.html")
)
