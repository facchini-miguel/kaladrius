from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import releases


@login_required
def lista(request):
    return render(
        request,
        "novidades/lista.html",
        {"versoes": releases.para_publico("equipe")},
    )
