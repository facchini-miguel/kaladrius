"""Team management by the clinic administrator: members, roles and access.

Vinculo is not an isolated model, so every query here filters by the current clinic
explicitly. Accounts are never deleted (the audit log refers to them): removing
someone from the clinic means turning their access off.
"""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.account import services as account_services
from apps.audit import events
from apps.audit.models import AuditEntry
from apps.audit.record import log_event
from apps.core.models import Membership
from apps.core.permissions import Action, Module, requires_permission

from .forms import MembershipForm, NewMemberForm, PasswordForm, UserAccountForm, exclusive_account


def _membership(request, pk):
    """A membership of the current clinic (404 for other clinics)."""
    return get_object_or_404(
        Membership.objects.select_related("user"), pk=pk, clinic=request.clinic
    )


@requires_permission(Module.USERS, Action.VIEW)
def member_list(request):
    memberships = (
        Membership.objects.filter(clinic=request.clinic)
        .select_related("user")
        .order_by("-active", "user__first_name", "user__username")
    )
    return render(request, "team/list.html", {"memberships": memberships})


@requires_permission(Module.USERS, Action.CREATE)
def new_member(request):
    form = NewMemberForm(request.POST or None, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        messages.success(
            request, _("%(name)s is now part of the team.") % {"name": user.get_full_name()}
        )
        return redirect("team:list")
    return render(request, "team/new.html", {"form": form})


@requires_permission(Module.USERS, Action.CHANGE)
def edit_member(request, pk):
    membership = _membership(request, pk)
    user = membership.user
    exclusive = exclusive_account(user, request.clinic)
    data = request.POST or None
    form = MembershipForm(data, instance=membership, editor=request.user, prefix="membership")
    account = UserAccountForm(data, instance=user, prefix="account") if exclusive else None
    if request.method == "POST" and form.is_valid() and (account is None or account.is_valid()):
        with transaction.atomic():
            form.save()
            if account is not None:
                account.save()
        messages.success(
            request, _("%(name)s's details saved.") % {"name": user.get_full_name() or user}
        )
        return redirect("team:list")
    return render(
        request,
        "team/edit.html",
        {
            "membership": membership,
            "form": form,
            "account": account,
            "exclusive": exclusive,
            "two_factor": account_services.active_for(user),
        },
    )


@requires_permission(Module.USERS, Action.CHANGE)
def password(request, pk):
    membership = _membership(request, pk)
    user = membership.user
    if user == request.user:
        return redirect("change_password")
    if not exclusive_account(user, request.clinic):
        messages.error(
            request,
            _(
                "%(name)s also has access to another clinic or to the platform: the password can "
                "only be changed by the user or by support."
            )
            % {"name": user},
        )
        return redirect("team:edit", pk=membership.pk)
    form = PasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            _("New password set for %(name)s.") % {"name": user.get_full_name() or user},
        )
        return redirect("team:list")
    return render(request, "team/password.html", {"membership": membership, "form": form})


@requires_permission(Module.USERS, Action.CHANGE)
def two_factor(request, pk):
    """Remove a member's two-step verification (lost phone, decision 111); they turn it on
    again with a new QR code."""
    membership = _membership(request, pk)
    user = membership.user
    if (
        request.method == "POST"
        and user != request.user
        and exclusive_account(user, request.clinic)
    ):
        account_services.deactivate(user)
        log_event(
            AuditEntry.Action.CHANGE,
            user,
            event=events.TWO_FACTOR_REMOVED,
            values={"record": user},
        )
        messages.success(
            request,
            _("Two-step verification of %(name)s removed.")
            % {"name": user.get_full_name() or user},
        )
    return redirect("team:edit", pk=membership.pk)
