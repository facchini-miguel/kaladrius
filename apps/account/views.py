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

from apps.audit.models import AuditEntry
from apps.audit.record import registrar

from . import services
from .forms import CodigoForm, DesativarForm, EntrarForm, NovaSenhaForm, RecuperarSenhaForm

PENDENTE = "duas_etapas_pendente"
VALIDADE_PENDENTE = 5 * 60  # seconds to type the code after the password
TENTATIVAS_CODIGO = 5


class EntrarView(auth_views.LoginView):
    authentication_form = EntrarForm

    def form_valid(self, form):
        user = form.get_user()
        if not services.ativa_para(user):
            return super().form_valid(form)
        # Password right: the code from the app comes next, before the session is opened.
        self.request.session[PENDENTE] = {
            "usuario": user.pk,
            "backend": user.backend,
            "momento": time.time(),
            "tentativas": 0,
            "proximo": self.get_success_url(),
        }
        return redirect("account:code")

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


def code(request):
    """Second step of the login: the 6-digit code of the app or a recovery code."""
    pendente = request.session.get(PENDENTE)
    if not pendente or time.time() - pendente["momento"] > VALIDADE_PENDENTE:
        request.session.pop(PENDENTE, None)
        messages.info(request, _("Entre de novo com o usuário e a senha."))
        return redirect("login")
    user = get_user_model().objects.get(pk=pendente["usuario"])
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if services.verificar(user, form.cleaned_data["code"]):
            del request.session[PENDENTE]
            login(request, user, backend=pendente["backend"])
            return redirect(pendente["proximo"])
        # Counted by the login protection too, so codes cannot be tried without end.
        user_login_failed.send(
            sender=__name__, credentials={"username": user.get_username()}, request=request
        )
        pendente["tentativas"] += 1
        if pendente["tentativas"] >= TENTATIVAS_CODIGO:
            del request.session[PENDENTE]
            messages.error(request, _("Muitos códigos errados. Entre de novo."))
            return redirect("login")
        request.session[PENDENTE] = pendente
        form.add_error("code", _("Código incorreto."))
    return render(request, "account/code.html", {"form": form})


@login_required
@require_GET
def active(request):
    """Called by the page while the person is using it, so 30 idle minutes are counted only
    when nobody touches the computer (the session is renewed on every request)."""
    return HttpResponse(status=204)


@login_required
def duas_etapas(request):
    """Turn two-step verification on (QR code) or off, and make new recovery codes."""
    # The real row, not the request's lazy user: the audit log needs its model.
    user = get_user_model().objects.get(pk=request.user.pk)
    if user.demonstracao:
        messages.info(request, _("Contas de demonstração não usam verificação em duas etapas."))
        return redirect("home")
    acao = request.POST.get("acao")
    obrigatoria = services.obrigatoria(request)
    if services.ativa_para(user):
        # Required by the clinic: it can only be renewed (new codes), not turned off.
        desativar = (
            None
            if obrigatoria
            else DesativarForm(
                request.POST if acao == "desativar" else None, user=user, prefix="desativar"
            )
        )
        novos = CodigoForm(request.POST if acao == "codigos" else None, prefix="codigos")
        if acao == "desativar" and desativar is not None and desativar.is_valid():
            services.desativar(user)
            registrar(
                AuditEntry.Acao.ALTERAR,
                user,
                description=f"{user}: verificação em duas etapas desativada",
            )
            messages.success(request, _("Verificação em duas etapas desativada."))
            return redirect("account:two_factor")
        if acao == "codigos" and novos.is_valid():
            if services.verificar(user, novos.cleaned_data["code"]):
                return render(
                    request,
                    "account/codes.html",
                    {"codigos": services.novos_codigos(user)},
                )
            novos.add_error("code", _("Código incorreto."))
        restantes = user.codigos_recuperacao.filter(usado_em__isnull=True).count()
        return render(
            request,
            "account/two_factor.html",
            {
                "active": True,
                "desativar": desativar,
                "novos": novos,
                "restantes": restantes,
                "obrigatoria": obrigatoria,
            },
        )
    dispositivo = services.preparar(user, novo=request.GET.get("novo") == "1")
    form = CodigoForm(request.POST if acao == "ativar" else None)
    if acao == "ativar" and form.is_valid():
        if services.verificar_app(dispositivo, form.cleaned_data["code"]):
            codigos = services.ativar(dispositivo)
            registrar(
                AuditEntry.Acao.ALTERAR,
                user,
                description=f"{user}: verificação em duas etapas ativada",
            )
            return render(request, "account/codes.html", {"codigos": codigos, "ativada": True})
        form.add_error("code", _("Código incorreto. Confira a hora do celular e tente de novo."))
    endereco = services.endereco_do_app(dispositivo)
    return render(
        request,
        "account/two_factor.html",
        {
            "active": False,
            "obrigatoria": obrigatoria,
            "form": form,
            "qr": services.qr_svg(endereco),
            "segredo": services.segredo_em_grupos(dispositivo.segredo),
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
        template_name="account/recover.html",
        email_template_name="account/recovery_email.txt",
        subject_template_name="account/recovery_email_subject.txt",
        extra_email_context={"nome_sistema": settings.NOME_SISTEMA},
        success_url=reverse_lazy("account:recovery_sent"),
    )
)
recuperar_enviado = _com_email(
    auth_views.PasswordResetDoneView.as_view(template_name="account/recovery_sent.html")
)
nova_senha = _com_email(
    auth_views.PasswordResetConfirmView.as_view(
        form_class=NovaSenhaForm,
        template_name="account/new_password.html",
        success_url=reverse_lazy("account:password_changed"),
    )
)
senha_redefinida = _com_email(
    auth_views.PasswordResetCompleteView.as_view(template_name="account/password_changed.html")
)
