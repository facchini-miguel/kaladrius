from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import dashboard
from .forms import ChangePasswordForm, ClinicForm, NewClinicForm
from .models import Clinic
from .permissions import Action, Module, requires_permission


def _greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return _("Bom dia")
    if hour < 18:
        return _("Boa tarde")
    return _("Boa noite")


@login_required
def start(request):
    context = {"greeting": _greeting()}
    if request.clinic is not None:
        context["dashboard"] = dashboard.build(request)
    return render(request, "core/home.html", context)


def _safe_destination(request, destination):
    if destination and url_has_allowed_host_and_scheme(
        destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destination
    return "home"


@login_required
def register_clinic(request):
    """First access of a new installation: the superuser registers the clinic. There is
    only one (decision 069), so once it exists this page sends to the home page."""
    if not request.user.is_superuser:
        raise PermissionDenied
    if Clinic.objects.exists():
        return redirect("home")
    form = NewClinicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Clínica cadastrada. Agora cadastre a equipe em Cadastros > Equipe.")
        )
        return redirect("home")
    return render(request, "core/register_clinic.html", {"form": form})


class ChangePasswordView(PasswordChangeView):
    """Any logged-in user can change their own password (keeps the session open)."""

    form_class = ChangePasswordForm
    template_name = "core/change_password.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "demo", False):
            messages.info(request, _("Contas de demonstração não trocam a senha."))
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, _("Senha alterada."))
        return super().form_valid(form)


@requires_permission(Module.CLINIC, Action.CHANGE)
def clinic_settings(request):
    form = ClinicForm(request.POST or None, instance=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Configurações da clínica salvas."))
        if "currency" in form.changed_data:
            messages.info(
                request,
                _("Os valores agora aparecem em %(moeda)s. Nenhum valor já lançado foi convertido.")
                % {"moeda": form.instance.get_currency_display()},
            )
        return redirect("clinic_settings")
    return render(request, "core/settings.html", {"form": form})


@login_required
@require_POST
def change_language(request):
    """Save the user's language (empty: follow the browser) and go back to the page."""
    language = request.POST.get("language", "")
    if language not in dict(settings.LANGUAGES):
        language = ""
    request.user.language = language
    request.user.save(update_fields=["language"])
    response = redirect(_safe_destination(request, request.POST.get("next")))
    # The cookie keeps the language on the login page of this browser too.
    if language:
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, language, max_age=365 * 24 * 3600, samesite="Lax"
        )
    else:
        response.delete_cookie(settings.LANGUAGE_COOKIE_NAME)
    return response
