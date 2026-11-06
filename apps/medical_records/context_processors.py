from .permissions import accesses_medical_records


def medical_records(request):
    # A callable: templates call it only where the menu or a page asks.
    return {"can_open_record": lambda: accesses_medical_records(request)}
