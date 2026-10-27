"""Estimate rules: approving (becomes a receivable) and refusing."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.financeiro import servicos as financeiro
from apps.financeiro.models import Lancamento

from .models import Orcamento


@transaction.atomic
def aprovar(orcamento, *, parcelas, primeiro_vencimento, categoria, usuario, pagamento=None):
    """Approve an open estimate: creates the receivable (and, optionally, pays the 1st
    installment with `pagamento` = {"forma": ..., "conta": ...}). Returns the receivable."""
    orcamento = Orcamento.objects.select_for_update().get(pk=orcamento.pk)
    if orcamento.situacao != Orcamento.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser aprovado."))
    total = orcamento.total
    if total <= 0:
        raise ValidationError(_("O orçamento não tem valor a receber."))
    lancamento = financeiro.criar_lancamento(
        clinica=orcamento.clinica,
        tipo=Lancamento.Tipo.RECEBER,
        paciente=orcamento.paciente,
        profissional=orcamento.profissional,
        descricao=_("Orçamento nº %(numero)s") % {"numero": orcamento.pk},
        categoria=categoria,
        valor_total=total,
        parcelas=parcelas,
        primeiro_vencimento=primeiro_vencimento,
        usuario=usuario,
    )
    if pagamento:
        primeira = lancamento.parcelas.order_by("numero").first()
        financeiro.receber(primeira, usuario=usuario, valor=primeira.valor, **pagamento)
    orcamento.situacao = Orcamento.Situacao.APROVADO
    orcamento.lancamento = lancamento
    orcamento.decidido_em = timezone.now()
    orcamento.decidido_por = usuario
    orcamento.save()
    return lancamento


@transaction.atomic
def recusar(orcamento, *, usuario):
    if orcamento.situacao != Orcamento.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser recusado."))
    orcamento.situacao = Orcamento.Situacao.RECUSADO
    orcamento.decidido_em = timezone.now()
    orcamento.decidido_por = usuario
    orcamento.save()
