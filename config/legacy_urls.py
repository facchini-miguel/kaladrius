"""The addresses before decision 155 (Portuguese), each a permanent redirect to its English one:
bookmarks, links in e-mails and pages opened before an update keep working. 308, not 301: the
method and body are kept, so a form opened before the update and sent after it still arrives.
The query string goes along, with the old filter names translated (decision 184), and the values
inside an address are translated."""

from django.http import HttpResponseRedirect, QueryDict
from django.urls import path, re_path, reverse

CATALOGS = {"categorias": "categories", "contas": "accounts", "centros-de-custo": "cost-centers"}
ACTIONS = {"conciliar": "reconcile", "ignorar": "ignore", "desfazer": "undo"}
CATALOG_PATTERN = "|".join(CATALOGS)
CASH_KINDS = {"retirada": "withdrawal", "reforco": "top-up"}
# Old query names (decisions 166 and 184); their values did not change.
QUERY_NAMES = {
    "pagina": "page",
    "de": "since",
    "ate": "until",
    "mes": "month",
    "periodo": "period",
    "agrupar": "group",
    "modulo": "module",
    "situacao": "status",
    "data": "date",
    "paciente": "patient",
}


class PermanentRedirect(HttpResponseRedirect):
    status_code = 308


def redirect_to(name, values=None):
    """A view that sends the old address to the URL named `nome`, with the same arguments."""

    def redirect_old(request, **kwargs):
        for key, translated in (values or {}).items():
            kwargs[key] = translated[kwargs[key]]
        destination = reverse(name, kwargs=kwargs)
        if request.GET:
            query = QueryDict(mutable=True)
            for key, query_values in request.GET.lists():
                query.setlist(QUERY_NAMES.get(key, key), query_values)
            destination += "?" + query.urlencode()
        return PermanentRedirect(destination)

    return redirect_old


urlpatterns = [
    path("agenda/", redirect_to("schedule:calendar")),
    path("agenda/eventos/", redirect_to("schedule:events")),
    path("agenda/novo/", redirect_to("schedule:new")),
    path("agenda/<int:pk>/editar/", redirect_to("schedule:edit")),
    path("agenda/<int:pk>/excluir/", redirect_to("schedule:delete")),
    path("agenda/<int:pk>/situacao/", redirect_to("schedule:status")),
    path("agenda/aniversariantes/", redirect_to("schedule:birthdays")),
    path("agenda/aniversariantes/dia/", redirect_to("schedule:birthdays_today")),
    path("agenda/tipos/", redirect_to("schedule:types")),
    path("agenda/tipos/novo/", redirect_to("schedule:type_new")),
    path("agenda/tipos/<int:pk>/editar/", redirect_to("schedule:type_edit")),
    path("agenda/tipos/<int:pk>/excluir/", redirect_to("schedule:type_delete")),
    path("ajuda/", redirect_to("help:index")),
    path("ajuda/tecnica/", redirect_to("help:technical_index")),
    path("ajuda/tecnica/<path:path>", redirect_to("help:technical")),
    path("ajuda/<slug:page>/", redirect_to("help:manual")),
    path("auditoria/", redirect_to("audit:list")),
    path("conta/login/codigo/", redirect_to("account:code")),
    path("conta/ativo/", redirect_to("account:active")),
    path("conta/duas-etapas/", redirect_to("account:two_factor")),
    path("conta/senha/esqueci/", redirect_to("account:recover")),
    path("conta/senha/esqueci/enviado/", redirect_to("account:recovery_sent")),
    path("conta/senha/nova/<uidb64>/<token>/", redirect_to("account:new_password")),
    path("conta/senha/redefinida/", redirect_to("account:password_changed")),
    path("convenios/", redirect_to("health_plans:list")),
    path("convenios/novo/", redirect_to("health_plans:new")),
    path("convenios/<int:pk>/editar/", redirect_to("health_plans:edit")),
    path("convenios/carteirinhas/nova/<int:patient>/", redirect_to("health_plans:card_new")),
    path("convenios/carteirinhas/<int:pk>/editar/", redirect_to("health_plans:card_edit")),
    path("equipe/", redirect_to("team:list")),
    path("equipe/novo/", redirect_to("team:new")),
    path("equipe/<int:pk>/editar/", redirect_to("team:edit")),
    path("equipe/<int:pk>/senha/", redirect_to("team:password")),
    path("equipe/<int:pk>/duas-etapas/", redirect_to("team:two_factor")),
    path("financeiro/receber/", redirect_to("finance:receivables")),
    path("financeiro/receber/novo/", redirect_to("finance:entry_new")),
    path("financeiro/lancamentos/<int:pk>/", redirect_to("finance:entry")),
    path("financeiro/lancamentos/<int:pk>/cancelar/", redirect_to("finance:cancel")),
    path("financeiro/parcelas/<int:pk>/receber/", redirect_to("finance:receive_installment")),
    path("financeiro/pagamentos/<int:pk>/recibo/", redirect_to("finance:receipt")),
    path("financeiro/pagamentos/<int:pk>/estornar/", redirect_to("finance:reverse_payment")),
    path("financeiro/devedores/", redirect_to("finance:debtors")),
    path("financeiro/pagar/", redirect_to("finance:payables")),
    path("financeiro/pagar/nova/", redirect_to("finance:expense_new")),
    path("financeiro/fluxo-de-caixa/", redirect_to("finance:cash_flow")),
    path("financeiro/caixa/", redirect_to("finance:cash")),
    path("financeiro/caixa/<int:pk>/", redirect_to("finance:cash_detail")),
    path("financeiro/caixa/<int:pk>/fechar/", redirect_to("finance:cash_close")),
    path(
        "financeiro/caixa/<int:pk>/<str:kind>/",
        redirect_to("finance:cash_movement", {"kind": CASH_KINDS}),
    ),
    path("financeiro/relatorios/", redirect_to("finance:reports")),
    path("financeiro/fechamento/", redirect_to("finance:closing")),
    path("financeiro/planejamento/", redirect_to("finance:planning")),
    path("financeiro/extratos/", redirect_to("finance:statements")),
    path("financeiro/extratos/<int:pk>/", redirect_to("finance:statement")),
    path("financeiro/extratos/<int:pk>/conciliar/", redirect_to("finance:statement_reconcile")),
    path("financeiro/transacoes/<int:pk>/lancamento/", redirect_to("finance:transaction_entry")),
    path("financeiro/plano-de-contas/", redirect_to("finance:chart_of_accounts")),
    path("financeiro/plano-de-contas/grupos/novo/", redirect_to("finance:group_new")),
    path("financeiro/plano-de-contas/grupos/<int:pk>/", redirect_to("finance:group_edit")),
    path("financeiro/fornecedores/", redirect_to("finance:suppliers")),
    path("financeiro/fornecedores/novo/", redirect_to("finance:supplier_new")),
    path("financeiro/fornecedores/<int:pk>/", redirect_to("finance:supplier")),
    path("financeiro/fornecedores/<int:pk>/editar/", redirect_to("finance:supplier_edit")),
    path("financeiro/comissoes/", redirect_to("finance:commissions")),
    path("financeiro/comissoes/<int:pk>/", redirect_to("finance:commission")),
    path(
        "financeiro/comissoes/profissional/<int:pk>/", redirect_to("finance:commission_percentage")
    ),
    path(
        "financeiro/comissoes/profissional/<int:pk>/pagar/", redirect_to("finance:commission_pay")
    ),
    path("sistema/saude/", redirect_to("monitoring:health")),
    path("orcamentos/", redirect_to("estimates:list")),
    path("orcamentos/novo/", redirect_to("estimates:new")),
    path("orcamentos/<int:pk>/", redirect_to("estimates:detail")),
    path("orcamentos/<int:pk>/editar/", redirect_to("estimates:edit")),
    path("orcamentos/<int:pk>/itens/", redirect_to("estimates:item_add")),
    path("orcamentos/<int:pk>/itens/<int:item>/remover/", redirect_to("estimates:item_remove")),
    path("orcamentos/<int:pk>/desconto/", redirect_to("estimates:discount")),
    path("orcamentos/<int:pk>/aprovar/", redirect_to("estimates:approve")),
    path("orcamentos/<int:pk>/recusar/", redirect_to("estimates:decline")),
    path("orcamentos/<int:pk>/imprimir/", redirect_to("estimates:print")),
    path("orcamentos/procedimentos/", redirect_to("estimates:procedures")),
    path("orcamentos/procedimentos/novo/", redirect_to("estimates:procedure_new")),
    path("orcamentos/procedimentos/<int:pk>/", redirect_to("estimates:procedure_edit")),
    path("pacientes/", redirect_to("patients:list")),
    path("pacientes/novo/", redirect_to("patients:new")),
    path("pacientes/sugestoes/", redirect_to("patients:suggestions")),
    path("pacientes/aniversariantes/", redirect_to("patients:birthdays")),
    path("pacientes/<int:pk>/", redirect_to("patients:record")),
    path("pacientes/<int:pk>/editar/", redirect_to("patients:edit")),
    path("pacientes/<int:pk>/imprimir/", redirect_to("patients:print")),
    path("pacientes/<int:pk>/arquivar/", redirect_to("patients:archive")),
    path("pacientes/<int:pk>/restaurar/", redirect_to("patients:restore")),
    path("pacientes/<int:pk>/excluir/", redirect_to("patients:delete")),
    path("pacientes/<int:pk>/relacionados/novo/", redirect_to("patients:related_new")),
    path("pacientes/relacionados/<int:pk>/", redirect_to("patients:related_edit")),
    path("pacientes/relacionados/<int:pk>/remover/", redirect_to("patients:related_remove")),
    path("pessoal/", redirect_to("staff:list")),
    path("pessoal/novo/", redirect_to("staff:new")),
    path("pessoal/<int:pk>/", redirect_to("staff:employee")),
    path("pessoal/<int:pk>/editar/", redirect_to("staff:edit")),
    path("pessoal/folha/", redirect_to("staff:payroll")),
    path("profissionais/", redirect_to("practitioners:list")),
    path("profissionais/novo/", redirect_to("practitioners:new")),
    path("profissionais/<int:pk>/editar/", redirect_to("practitioners:edit")),
    path("profissionais/<int:pk>/excluir/", redirect_to("practitioners:delete")),
    path("prontuario/pacientes/<int:patient>/novo/", redirect_to("medical_records:new")),
    path("prontuario/<int:pk>/", redirect_to("medical_records:visit")),
    path("prontuario/<int:pk>/adendo/", redirect_to("medical_records:addendum")),
    path("prontuario/<int:pk>/imprimir/", redirect_to("medical_records:print")),
    path("prontuario/<int:pk>/atestado/", redirect_to("medical_records:certificate_new")),
    path("prontuario/<int:pk>/receita/", redirect_to("medical_records:prescription_new")),
    path("prontuario/atestados/<int:pk>/", redirect_to("medical_records:certificate")),
    path("prontuario/receitas/<int:pk>/", redirect_to("medical_records:prescription")),
    path("prontuario/<int:pk>/exames/", redirect_to("medical_records:exam_request_new")),
    path("prontuario/exames/<int:pk>/", redirect_to("medical_records:exam_request")),
    path("prontuario/<int:pk>/anexos/", redirect_to("medical_records:attachment_upload")),
    path("prontuario/anexos/<int:pk>/", redirect_to("medical_records:attachment")),
    path("prontuario/anexos/<int:pk>/remover/", redirect_to("medical_records:attachment_remove")),
    path("rechamadas/", redirect_to("recalls:list")),
    path("rechamadas/novo/", redirect_to("recalls:new")),
    path("rechamadas/<int:pk>/editar/", redirect_to("recalls:edit")),
    path("rechamadas/<int:pk>/concluir/", redirect_to("recalls:complete")),
    path("rechamadas/<int:pk>/excluir/", redirect_to("recalls:delete")),
    path("rechamadas/resumo/", redirect_to("recalls:summary")),
    path("rechamadas/dia/", redirect_to("recalls:today")),
    path("referencias/cidades/", redirect_to("reference_data:cities")),
    path("referencias/cidades/opcoes/", redirect_to("reference_data:city_options")),
    path("referencias/enderecos/sugestoes/", redirect_to("reference_data:address_suggestions")),
    path("referencias/bancos/", redirect_to("reference_data:banks")),
    path("conta/login/", redirect_to("login")),
    path("conta/logout/", redirect_to("logout")),
    path("clinica/cadastrar/", redirect_to("register_clinic")),
    path("clinica/configuracoes/", redirect_to("clinic_settings")),
    path("conta/senha/", redirect_to("change_password")),
    path("conta/idioma/", redirect_to("change_language")),
    path("privacidade/", redirect_to("privacy")),
    path("novidades/", redirect_to("whats_new")),
    re_path(
        r"^financeiro/(?P<catalog>categorias|contas|centros-de-custo)/$",
        redirect_to("finance:catalog", {"catalog": CATALOGS}),
    ),
    re_path(
        r"^financeiro/(?P<catalog>categorias|contas|centros-de-custo)/novo/$",
        redirect_to("finance:catalog_new", {"catalog": CATALOGS}),
    ),
    re_path(
        rf"^financeiro/(?P<catalog>{CATALOG_PATTERN})/(?P<pk>[0-9]+)/$",
        redirect_to("finance:catalog_edit", {"catalog": CATALOGS}),
    ),
    re_path(
        r"^financeiro/transacoes/(?P<pk>[0-9]+)/(?P<action>conciliar|ignorar|desfazer)/$",
        redirect_to("finance:transaction", {"action": ACTIONS}),
    ),
]
