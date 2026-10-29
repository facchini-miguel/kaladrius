from .permissoes import profissional_do_usuario


def prontuario(request):
    # A callable: templates call it only where the menu or a page asks.
    return {"pode_prontuario": lambda: profissional_do_usuario(request) is not None}
