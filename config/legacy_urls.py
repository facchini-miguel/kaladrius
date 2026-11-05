"""The addresses before decision 155 (Portuguese), each a permanent redirect to its English one:
bookmarks, links in e-mails and pages opened before an update keep working. 308, not 301: the
method and body are kept, so a form opened before the update and sent after it still arrives.
The query string goes along, and the values inside an address are translated."""

from django.http import HttpResponseRedirect
from django.urls import path, re_path, reverse

CATALOGS = {"categorias": "categories", "contas": "accounts", "centros-de-custo": "cost-centers"}
ACOES = {"conciliar": "reconcile", "ignorar": "ignore", "desfazer": "undo"}
CADASTRO = "|".join(CATALOGS)
CAIXA = {"retirada": "withdrawal", "reforco": "top-up"}


class RedirecionamentoPermanente(HttpResponseRedirect):
    status_code = 308


def para(name, valores=None):
    """A view that sends the old address to the URL named `nome`, with the same arguments."""

    def redirecionar(request, **kwargs):
        for key, traducao in (valores or {}).items():
            kwargs[key] = traducao[kwargs[key]]
        destino = reverse(name, kwargs=kwargs)
        if request.META.get("QUERY_STRING"):
            destino += "?" + request.META["QUERY_STRING"]
        return RedirecionamentoPermanente(destino)

    return redirecionar


urlpatterns = [
    path("agenda/", para("schedule:calendar")),
    path("agenda/eventos/", para("schedule:events")),
    path("agenda/novo/", para("schedule:new")),
    path("agenda/<int:pk>/editar/", para("schedule:edit")),
    path("agenda/<int:pk>/excluir/", para("schedule:delete")),
    path("agenda/<int:pk>/situacao/", para("schedule:status")),
    path("agenda/aniversariantes/", para("schedule:birthdays")),
    path("agenda/aniversariantes/dia/", para("schedule:birthdays_today")),
    path("agenda/tipos/", para("schedule:types")),
    path("agenda/tipos/novo/", para("schedule:type_new")),
    path("agenda/tipos/<int:pk>/editar/", para("schedule:type_edit")),
    path("agenda/tipos/<int:pk>/excluir/", para("schedule:type_delete")),
    path("ajuda/", para("help:index")),
    path("ajuda/tecnica/", para("help:technical_index")),
    path("ajuda/tecnica/<path:path>", para("help:technical")),
    path("ajuda/<slug:page>/", para("help:manual")),
    path("auditoria/", para("audit:list")),
    path("conta/login/codigo/", para("account:code")),
    path("conta/ativo/", para("account:active")),
    path("conta/duas-etapas/", para("account:two_factor")),
    path("conta/senha/esqueci/", para("account:recover")),
    path("conta/senha/esqueci/enviado/", para("account:recovery_sent")),
    path("conta/senha/nova/<uidb64>/<token>/", para("account:new_password")),
    path("conta/senha/redefinida/", para("account:password_changed")),
    path("convenios/", para("health_plans:list")),
    path("convenios/novo/", para("health_plans:new")),
    path("convenios/<int:pk>/editar/", para("health_plans:edit")),
    path("convenios/carteirinhas/nova/<int:patient>/", para("health_plans:card_new")),
    path("convenios/carteirinhas/<int:pk>/editar/", para("health_plans:card_edit")),
    path("equipe/", para("team:list")),
    path("equipe/novo/", para("team:new")),
    path("equipe/<int:pk>/editar/", para("team:edit")),
    path("equipe/<int:pk>/senha/", para("team:password")),
    path("equipe/<int:pk>/duas-etapas/", para("team:two_factor")),
    path("financeiro/receber/", para("finance:receivables")),
    path("financeiro/receber/novo/", para("finance:entry_new")),
    path("financeiro/lancamentos/<int:pk>/", para("finance:entry")),
    path("financeiro/lancamentos/<int:pk>/cancelar/", para("finance:cancel")),
    path("financeiro/parcelas/<int:pk>/receber/", para("finance:receive_installment")),
    path("financeiro/pagamentos/<int:pk>/recibo/", para("finance:receipt")),
    path("financeiro/pagamentos/<int:pk>/estornar/", para("finance:reverse_payment")),
    path("financeiro/devedores/", para("finance:debtors")),
    path("financeiro/pagar/", para("finance:payables")),
    path("financeiro/pagar/nova/", para("finance:expense_new")),
    path("financeiro/fluxo-de-caixa/", para("finance:cash_flow")),
    path("financeiro/caixa/", para("finance:cash")),
    path("financeiro/caixa/<int:pk>/", para("finance:cash_detail")),
    path("financeiro/caixa/<int:pk>/fechar/", para("finance:cash_close")),
    path("financeiro/caixa/<int:pk>/<str:kind>/", para("finance:cash_movement", {"kind": CAIXA})),
    path("financeiro/relatorios/", para("finance:reports")),
    path("financeiro/fechamento/", para("finance:closing")),
    path("financeiro/planejamento/", para("finance:planning")),
    path("financeiro/extratos/", para("finance:statements")),
    path("financeiro/extratos/<int:pk>/", para("finance:statement")),
    path("financeiro/extratos/<int:pk>/conciliar/", para("finance:statement_reconcile")),
    path("financeiro/transacoes/<int:pk>/lancamento/", para("finance:transaction_entry")),
    path("financeiro/plano-de-contas/", para("finance:chart_of_accounts")),
    path("financeiro/plano-de-contas/grupos/novo/", para("finance:group_new")),
    path("financeiro/plano-de-contas/grupos/<int:pk>/", para("finance:group_edit")),
    path("financeiro/fornecedores/", para("finance:suppliers")),
    path("financeiro/fornecedores/novo/", para("finance:supplier_new")),
    path("financeiro/fornecedores/<int:pk>/", para("finance:supplier")),
    path("financeiro/fornecedores/<int:pk>/editar/", para("finance:supplier_edit")),
    path("financeiro/comissoes/", para("finance:commissions")),
    path("financeiro/comissoes/<int:pk>/", para("finance:commission")),
    path("financeiro/comissoes/profissional/<int:pk>/", para("finance:commission_percentage")),
    path("financeiro/comissoes/profissional/<int:pk>/pagar/", para("finance:commission_pay")),
    path("sistema/saude/", para("monitoring:health")),
    path("orcamentos/", para("estimates:list")),
    path("orcamentos/novo/", para("estimates:new")),
    path("orcamentos/<int:pk>/", para("estimates:detail")),
    path("orcamentos/<int:pk>/editar/", para("estimates:edit")),
    path("orcamentos/<int:pk>/itens/", para("estimates:item_add")),
    path("orcamentos/<int:pk>/itens/<int:item>/remover/", para("estimates:item_remove")),
    path("orcamentos/<int:pk>/desconto/", para("estimates:discount")),
    path("orcamentos/<int:pk>/aprovar/", para("estimates:approve")),
    path("orcamentos/<int:pk>/recusar/", para("estimates:decline")),
    path("orcamentos/<int:pk>/imprimir/", para("estimates:print")),
    path("orcamentos/procedimentos/", para("estimates:procedures")),
    path("orcamentos/procedimentos/novo/", para("estimates:procedure_new")),
    path("orcamentos/procedimentos/<int:pk>/", para("estimates:procedure_edit")),
    path("pacientes/", para("patients:list")),
    path("pacientes/novo/", para("patients:new")),
    path("pacientes/sugestoes/", para("patients:suggestions")),
    path("pacientes/aniversariantes/", para("patients:birthdays")),
    path("pacientes/<int:pk>/", para("patients:record")),
    path("pacientes/<int:pk>/editar/", para("patients:edit")),
    path("pacientes/<int:pk>/imprimir/", para("patients:print")),
    path("pacientes/<int:pk>/arquivar/", para("patients:archive")),
    path("pacientes/<int:pk>/restaurar/", para("patients:restore")),
    path("pacientes/<int:pk>/excluir/", para("patients:delete")),
    path("pacientes/<int:pk>/relacionados/novo/", para("patients:related_new")),
    path("pacientes/relacionados/<int:pk>/", para("patients:related_edit")),
    path("pacientes/relacionados/<int:pk>/remover/", para("patients:related_remove")),
    path("pessoal/", para("staff:list")),
    path("pessoal/novo/", para("staff:new")),
    path("pessoal/<int:pk>/", para("staff:employee")),
    path("pessoal/<int:pk>/editar/", para("staff:edit")),
    path("pessoal/folha/", para("staff:payroll")),
    path("profissionais/", para("practitioners:list")),
    path("profissionais/novo/", para("practitioners:new")),
    path("profissionais/<int:pk>/editar/", para("practitioners:edit")),
    path("profissionais/<int:pk>/excluir/", para("practitioners:delete")),
    path("prontuario/pacientes/<int:patient>/novo/", para("medical_records:new")),
    path("prontuario/<int:pk>/", para("medical_records:visit")),
    path("prontuario/<int:pk>/adendo/", para("medical_records:addendum")),
    path("prontuario/<int:pk>/imprimir/", para("medical_records:print")),
    path("prontuario/<int:pk>/atestado/", para("medical_records:certificate_new")),
    path("prontuario/<int:pk>/receita/", para("medical_records:prescription_new")),
    path("prontuario/atestados/<int:pk>/", para("medical_records:certificate")),
    path("prontuario/receitas/<int:pk>/", para("medical_records:prescription")),
    path("prontuario/<int:pk>/exames/", para("medical_records:exam_request_new")),
    path("prontuario/exames/<int:pk>/", para("medical_records:exam_request")),
    path("prontuario/<int:pk>/anexos/", para("medical_records:attachment_upload")),
    path("prontuario/anexos/<int:pk>/", para("medical_records:attachment")),
    path("prontuario/anexos/<int:pk>/remover/", para("medical_records:attachment_remove")),
    path("rechamadas/", para("recalls:list")),
    path("rechamadas/novo/", para("recalls:new")),
    path("rechamadas/<int:pk>/editar/", para("recalls:edit")),
    path("rechamadas/<int:pk>/concluir/", para("recalls:complete")),
    path("rechamadas/<int:pk>/excluir/", para("recalls:delete")),
    path("rechamadas/resumo/", para("recalls:summary")),
    path("rechamadas/dia/", para("recalls:today")),
    path("referencias/cidades/", para("reference_data:cities")),
    path("referencias/cidades/opcoes/", para("reference_data:city_options")),
    path("referencias/enderecos/sugestoes/", para("reference_data:address_suggestions")),
    path("referencias/bancos/", para("reference_data:banks")),
    path("conta/login/", para("login")),
    path("conta/logout/", para("logout")),
    path("clinica/cadastrar/", para("register_clinic")),
    path("clinica/configuracoes/", para("clinic_settings")),
    path("conta/senha/", para("change_password")),
    path("conta/idioma/", para("change_language")),
    path("privacidade/", para("privacy")),
    path("novidades/", para("whats_new")),
    re_path(
        r"^financeiro/(?P<cadastro>categorias|contas|centros-de-custo)/$",
        para("finance:catalog", {"cadastro": CATALOGS}),
    ),
    re_path(
        r"^financeiro/(?P<cadastro>categorias|contas|centros-de-custo)/novo/$",
        para("finance:catalog_new", {"cadastro": CATALOGS}),
    ),
    re_path(
        rf"^financeiro/(?P<cadastro>{CADASTRO})/(?P<pk>[0-9]+)/$",
        para("finance:catalog_edit", {"cadastro": CATALOGS}),
    ),
    re_path(
        r"^financeiro/transacoes/(?P<pk>[0-9]+)/(?P<acao>conciliar|ignorar|desfazer)/$",
        para("finance:transaction", {"acao": ACOES}),
    ),
]
