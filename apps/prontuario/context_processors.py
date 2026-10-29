from .permissoes import acessa_prontuario


def prontuario(request):
    # A callable: templates call it only where the menu or a page asks.
    return {"pode_prontuario": lambda: acessa_prontuario(request)}
