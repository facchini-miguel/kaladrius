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

from apps.audit import events
from apps.audit.models import AuditEntry
from apps.audit.record import log_event

from . import services
from .forms import CodeForm, DisableTwoFactorForm, LoginForm, NewPasswordForm, RecoverPasswordForm

PENDING = "two_factor_pending"
PENDING_VALIDITY = 5 * 60  # seconds to type the code after the password
CODE_ATTEMPTS = 5


class ClinicLoginView(auth_views.LoginView):
    authentication_form = LoginForm

    def form_valid(self, form):
        user = form.get_user()
        if not services.active_for(user):
            return super().form_valid(form)
        # Password right: the code from the app comes next, before the session is opened.
        self.request.session[PENDING] = {
            "usuario": user.pk,
            "backend": user.backend,
            "time": time.time(),
            "attempts": 0,
            "proximo": self.get_success_url(),
        }
        return redirect("account:code")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        errors = context["form"].non_field_errors().as_data()
        return {
            **context,
            "address_locked": any(e.code == "address_locked" for e in errors),
            "recovery_by_email": settings.PASSWORD_RECOVERY_BY_EMAIL,
            "idle": self.request.GET.get("idle") == "1",
            "minutes": settings.IDLE_MINUTES,
        }


def code(request):
    """Second step of the login: the 6-digit code of the app or a recovery code."""
    pending_login = request.session.get(PENDING)
    if not pending_login or time.time() - pending_login["time"] > PENDING_VALIDITY:
        request.session.pop(PENDING, None)
        messages.info(request, _("Log in again with the username and password."))
        return redirect("login")
    user = get_user_model().objects.get(pk=pending_login["usuario"])
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if services.verify(user, form.cleaned_data["code"]):
            del request.session[PENDING]
            login(request, user, backend=pending_login["backend"])
            return redirect(pending_login["proximo"])
        # Counted by the login protection too, so codes cannot be tried without end.
        user_login_failed.send(
            sender=__name__, credentials={"username": user.get_username()}, request=request
        )
        pending_login["attempts"] += 1
        if pending_login["attempts"] >= CODE_ATTEMPTS:
            del request.session[PENDING]
            messages.error(request, _("Too many wrong codes. Log in again."))
            return redirect("login")
        request.session[PENDING] = pending_login
        form.add_error("code", _("Wrong code."))
    return render(request, "account/code.html", {"form": form})


@login_required
@require_GET
def active(request):
    """Called by the page while the person is using it, so 30 idle minutes are counted only
    when nobody touches the computer (the session is renewed on every request)."""
    return HttpResponse(status=204)


@login_required
def two_factor(request):
    """Turn two-step verification on (QR code) or off, and make new recovery codes."""
    # The real row, not the request's lazy user: the audit log needs its model.
    user = get_user_model().objects.get(pk=request.user.pk)
    if user.demo:
        messages.info(request, _("Demo accounts do not use two-step verification."))
        return redirect("home")
    action = request.POST.get("action")
    is_required = services.is_required(request)
    if services.active_for(user):
        # Required by the clinic: it can only be renewed (new codes), not turned off.
        deactivate = (
            None
            if is_required
            else DisableTwoFactorForm(
                request.POST if action == "disable" else None, user=user, prefix="disable"
            )
        )
        new_ones = CodeForm(request.POST if action == "codigos" else None, prefix="codes")
        if action == "disable" and deactivate is not None and deactivate.is_valid():
            services.deactivate(user)
            log_event(
                AuditEntry.Action.CHANGE,
                user,
                event=events.TWO_FACTOR_OFF,
                values={"record": user},
            )
            messages.success(request, _("Two-step verification turned off."))
            return redirect("account:two_factor")
        if action == "codigos" and new_ones.is_valid():
            if services.verify(user, new_ones.cleaned_data["code"]):
                return render(
                    request,
                    "account/codes.html",
                    {"codes": services.new_codes(user)},
                )
            new_ones.add_error("code", _("Wrong code."))
        remaining_ones = user.recovery_codes.filter(used_at__isnull=True).count()
        return render(
            request,
            "account/two_factor.html",
            {
                "active": True,
                "disable_form": deactivate,
                "codes_form": new_ones,
                "remaining": remaining_ones,
                "required": is_required,
            },
        )
    device = services.prepare(user, new=request.GET.get("new") == "1")
    form = CodeForm(request.POST if action == "enable" else None)
    if action == "enable" and form.is_valid():
        if services.verify_app(device, form.cleaned_data["code"]):
            codes = services.activate(device)
            log_event(
                AuditEntry.Action.CHANGE,
                user,
                event=events.TWO_FACTOR_ON,
                values={"record": user},
            )
            return render(request, "account/codes.html", {"codes": codes, "enabled": True})
        form.add_error("code", _("Wrong code. Check the phone's clock and try again."))
    address = services.app_uri(device)
    return render(
        request,
        "account/two_factor.html",
        {
            "active": False,
            "required": is_required,
            "form": form,
            "qr": services.qr_svg(address),
            "secret": services.secret_in_groups(device.secret),
        },
    )


def _with_email(view):
    """Password recovery only exists where the installation can send e-mail."""

    def protected(request, *args, **kwargs):
        if not settings.PASSWORD_RECOVERY_BY_EMAIL:
            raise Http404
        return view(request, *args, **kwargs)

    return protected


password_recover = _with_email(
    auth_views.PasswordResetView.as_view(
        form_class=RecoverPasswordForm,
        template_name="account/recover.html",
        email_template_name="account/recovery_email.txt",
        subject_template_name="account/recovery_email_subject.txt",
        extra_email_context={"system_name": settings.SYSTEM_NAME},
        success_url=reverse_lazy("account:recovery_sent"),
    )
)
password_recover_sent = _with_email(
    auth_views.PasswordResetDoneView.as_view(template_name="account/recovery_sent.html")
)
new_password = _with_email(
    auth_views.PasswordResetConfirmView.as_view(
        form_class=NewPasswordForm,
        template_name="account/new_password.html",
        success_url=reverse_lazy("account:password_changed"),
    )
)
password_reset_done = _with_email(
    auth_views.PasswordResetCompleteView.as_view(template_name="account/password_changed.html")
)
