"""The month's pay (decision 099): prepared per employee, then launched as payables."""

import calendar
import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.ordem import chave_alfabetica
from apps.financeiro import servicos as financeiro
from apps.financeiro.models import Lancamento

from .models import Folha, Funcionario, hora_extra_sugerida


def competencia_de(data):
    return data.replace(day=1)


def fim_do_mes(competencia):
    return competencia.replace(day=calendar.monthrange(competencia.year, competencia.month)[1])


def preparar(competencia):
    """The month's sheets: one per employee working in the month that has a salary.

    Sheets already saved keep what was typed; the missing ones come unsaved, with the
    salary in force at the end of the month and the suggested overtime hour. Only saving
    the page stores them, so looking at a month (even a future one) leaves nothing behind.
    """
    fim = fim_do_mes(competencia)
    trabalhando = (
        Funcionario.objects.filter(ativo=True)
        .exclude(admissao__gt=fim)
        .exclude(desligamento__lt=competencia)
    )
    folhas = list(
        Folha.objects.filter(competencia=competencia).select_related("funcionario", "lancamento")
    )
    existentes = {f.funcionario_id for f in folhas}
    for funcionario in trabalhando:
        salario = funcionario.salario_em(fim)
        if funcionario.pk in existentes or salario is None:
            continue
        folhas.append(
            Folha(
                funcionario=funcionario,
                competencia=competencia,
                salario=salario,
                valor_hora_extra=hora_extra_sugerida(salario),
            )
        )
    return sorted(folhas, key=lambda f: chave_alfabetica(f.funcionario.nome))


@transaction.atomic
def lancar(folhas, *, categoria, vencimento, usuario):
    """Turn the sheets not yet launched into payables, one per employee."""
    lancadas = 0
    for folha in folhas:
        folha = Folha.objects.select_for_update().select_related("funcionario").get(pk=folha.pk)
        if folha.lancada:
            continue
        if folha.total <= 0:
            raise ValidationError(
                _("O total de %(nome)s precisa ser maior que zero.") % {"nome": folha.funcionario}
            )
        mes = f"{folha.competencia:%m/%Y}"
        folha.lancamento = financeiro.criar_lancamento(
            clinica=folha.funcionario.clinica,
            tipo=Lancamento.Tipo.PAGAR,
            pessoa=folha.funcionario.nome,
            descricao=_("Salário %(mes)s") % {"mes": mes},
            categoria=categoria,
            observacoes=_("Salário %(salario)s + horas extras %(extras)s − faltas %(faltas)s.")
            % {
                "salario": folha.salario,
                "extras": folha.valor_horas_extras,
                "faltas": folha.desconto_faltas,
            },
            valor_total=folha.total,
            parcelas=1,
            primeiro_vencimento=vencimento,
            usuario=usuario,
        )
        folha.save(update_fields=["lancamento"])
        lancadas += 1
    return lancadas


def mes_da_url(texto, hoje):
    """The month asked as YYYY-MM, or the current one."""
    try:
        return datetime.datetime.strptime(texto or "", "%Y-%m").date()
    except ValueError:
        return competencia_de(hoje)
