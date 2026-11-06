from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import releases


@login_required
def whats_new_list(request):
    versions = releases.for_audience("equipe")
    modules = sorted({(item.module, item.module_name) for _, items in versions for item in items})
    module = request.GET.get("module", "")
    if module:
        versions = [
            (release, tuple(item for item in items if item.module == module))
            for release, items in versions
        ]
        versions = [(release, items) for release, items in versions if items]

    # Opening this page clears the "new version" notice.
    current = releases.current_version()
    if request.user.last_seen_version != current:
        request.user.last_seen_version = current
        request.user.save(update_fields=["last_seen_version"])

    return render(
        request,
        "whats_new/list.html",
        {"versions": versions, "modules": modules, "module": module},
    )
