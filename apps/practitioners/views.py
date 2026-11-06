from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissions import Action, Module, requires_permission

from .forms import PractitionerForm
from .models import Practitioner


@requires_permission(Module.PRACTITIONERS, Action.VIEW)
def practitioner_list(request):
    profissionais = Practitioner.objects.select_related("user")
    return render(request, "practitioners/list.html", {"practitioners": profissionais})


@requires_permission(Module.PRACTITIONERS, Action.CREATE)
def new_practitioner(request):
    return _practitioner_form(request, Practitioner())


@requires_permission(Module.PRACTITIONERS, Action.CHANGE)
def edit_practitioner(request, pk):
    # Profissional.objects only sees the current clinic: other clinics' ids give 404.
    return _practitioner_form(request, get_object_or_404(Practitioner.objects, pk=pk))


def _practitioner_form(request, practitioner):
    form = PractitionerForm(request.POST or None, instance=practitioner, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profissional %(nome)s salvo.") % {"nome": practitioner.name})
        return redirect("practitioners:list")
    return render(request, "practitioners/form.html", {"form": form, "practitioner": practitioner})


@requires_permission(Module.PRACTITIONERS, Action.DELETE)
def delete_practitioner(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    if request.method == "POST":
        try:
            practitioner.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "%(nome)s tem registros ligados e não pode ser excluído. "
                    "Desmarque “ativo” para escondê-lo."
                )
                % {"nome": practitioner.name},
            )
        else:
            messages.success(
                request, _("Profissional %(nome)s excluído.") % {"nome": practitioner.name}
            )
        return redirect("practitioners:list")
    return render(request, "practitioners/delete.html", {"practitioner": practitioner})
