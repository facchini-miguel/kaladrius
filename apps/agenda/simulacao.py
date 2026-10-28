"""Fake schedule and recalls around today, for test clinics (fake data, not security).

Used by popular_dados_teste and by simular_movimento (for a clinic whose own data is
anonymized test data). Only active, non-archived patients and active practitioners take
part, and slots already taken are skipped, so the overlap constraint is never hit.
"""

import datetime

from django.utils import timezone

from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

from .models import Agendamento, TipoAtendimento
from .servicos import momento

MOTIVOS_RECHAMADA = ["Revisão de 6 meses", "Retorno pós-procedimento", "Limpeza", "Reavaliação"]


def _pacientes(clinica):
    return list(Paciente.objects.filter(clinica=clinica, ativo=True, arquivado=False))


def simular_agendamentos(clinica, sorteio, semanas_antes=2, semanas_depois=4, ocupacao=0.6):
    """Fill about `ocupacao` of the free weekday slots around today. Returns how many."""
    profissionais = list(Profissional.objects.filter(clinica=clinica, ativo=True))
    tipos = list(
        TipoAtendimento.objects.filter(clinica=clinica, ativo=True).exclude(
            nome__in=["Liberado", "Ocupado"]
        )
    )
    pacientes = _pacientes(clinica)
    if not (profissionais and tipos and pacientes):
        return 0
    passo = datetime.timedelta(minutes=clinica.agenda_intervalo)
    hoje = timezone.localdate()
    segunda = hoje - datetime.timedelta(days=hoje.weekday() + 7 * semanas_antes)
    dias = [
        segunda + datetime.timedelta(days=n) for n in range(7 * (semanas_antes + semanas_depois))
    ]
    ocupados = {}
    for profissional_id, inicio, fim in Agendamento.objects.filter(
        clinica=clinica,
        inicio__lt=momento(dias[-1], datetime.time(23, 59)),
        fim__gt=momento(dias[0], datetime.time(0)),
    ).values_list("profissional_id", "inicio", "fim"):
        ocupados.setdefault(profissional_id, []).append((inicio, fim))

    def livre(profissional, inicio, fim):
        return all(fim <= a or inicio >= b for a, b in ocupados.get(profissional.pk, []))

    novos = []
    for dia in dias:
        if dia.weekday() >= 5:
            continue
        for profissional in profissionais:
            atual = momento(dia, clinica.agenda_inicio)
            fim_do_dia = momento(dia, clinica.agenda_fim)
            while atual < fim_do_dia:
                duracao = passo * sorteio.choice([1, 1, 2])
                fim = atual + duracao
                if (
                    fim > fim_do_dia
                    or sorteio.random() > ocupacao
                    or not livre(profissional, atual, fim)
                ):
                    atual += passo
                    continue
                com_paciente = sorteio.random() < 0.9
                novos.append(
                    Agendamento(
                        clinica=clinica,
                        profissional=profissional,
                        tipo=sorteio.choice(tipos),
                        paciente=sorteio.choice(pacientes) if com_paciente else None,
                        descricao="" if com_paciente else "Horário bloqueado",
                        situacao=_situacao(sorteio, atual) if com_paciente else "agendado",
                        inicio=atual,
                        fim=fim,
                    )
                )
                atual = fim
    Agendamento.objects.bulk_create(novos, batch_size=1000)
    return len(novos)


def _situacao(sorteio, inicio):
    """Past appointments: most patients came, some missed or cancelled (0.24.0)."""
    if inicio > timezone.now():
        return Agendamento.Situacao.AGENDADO
    sorteado = sorteio.random()
    if sorteado < 0.82:
        return Agendamento.Situacao.COMPARECEU
    if sorteado < 0.92:
        return Agendamento.Situacao.FALTOU
    return Agendamento.Situacao.DESMARCOU


def simular_rechamadas(clinica, sorteio, quantidade=80, dias_antes=30, dias_depois=60):
    """Recalls from `dias_antes` ago to `dias_depois` ahead; past ones mostly done."""
    pacientes = _pacientes(clinica)
    if not pacientes:
        return 0
    hoje = timezone.localdate()
    novas = []
    for _ in range(quantidade):
        data = hoje + datetime.timedelta(days=sorteio.randint(-dias_antes, dias_depois))
        novas.append(
            Rechamada(
                clinica=clinica,
                paciente=sorteio.choice(pacientes),
                data=data,
                descricao=sorteio.choice(MOTIVOS_RECHAMADA),
                concluida=data < hoje and sorteio.random() < 0.7,
            )
        )
    Rechamada.objects.bulk_create(novas)
    return len(novas)


DESCRICOES_FINANCEIRAS = [
    "Limpeza",
    "Restauração",
    "Tratamento de canal",
    "Prótese",
    "Clareamento",
    "Aparelho ortodôntico",
    "Extração",
    "Consulta",
]


def simular_financeiro(clinica, sorteio, quantidade=60, usuario=None):
    """Fake receivables from 90 days ago to today, in 1 to 6 installments.

    Installments due in the past are mostly paid (some are left overdue, for the debtors
    report); the first one of some entries is paid on the spot.
    """
    from decimal import Decimal

    from apps.financeiro import servicos
    from apps.financeiro.models import Categoria, Conta, Lancamento, Pagamento

    pacientes = _pacientes(clinica)
    categorias = list(Categoria.objects.filter(clinica=clinica, tipo=Categoria.Tipo.RECEITA))
    contas = list(Conta.objects.filter(clinica=clinica, ativa=True))
    profissionais = list(Profissional.objects.filter(clinica=clinica, ativo=True))
    if not (pacientes and categorias and contas):
        return 0, 0
    hoje = timezone.localdate()
    formas = [forma for forma, _rotulo in Pagamento.Forma.choices]
    criados = 0
    for _ in range(quantidade):
        data = hoje - datetime.timedelta(days=sorteio.randint(0, 90))
        lancamento = servicos.criar_lancamento(
            clinica=clinica,
            tipo=Lancamento.Tipo.RECEBER,
            paciente=sorteio.choice(pacientes),
            descricao=sorteio.choice(DESCRICOES_FINANCEIRAS),
            categoria=sorteio.choice(categorias),
            profissional=sorteio.choice(profissionais) if profissionais else None,
            valor_total=Decimal(sorteio.randrange(150, 3000, 10)),
            data=data,
            parcelas=sorteio.choice([1, 1, 2, 3, 4, 6]),
            primeiro_vencimento=data,
            usuario=usuario,
        )
        for parcela in lancamento.parcelas.all():
            if parcela.vencimento <= hoje and sorteio.random() < 0.8:
                servicos.receber(
                    parcela,
                    usuario=usuario,
                    valor=parcela.valor,
                    data=parcela.vencimento,
                    forma=sorteio.choice(formas),
                    conta=sorteio.choice(contas),
                )
        criados += 1
    return criados, _simular_despesas(clinica, sorteio, contas, usuario)


# Fake payables: (supplier, description, category, amount, monthly repetitions or None).
DESPESAS_SIMULADAS = [
    ("Imobiliária Central", "Aluguel", "Aluguel", 3000, 6),
    ("Companhia de energia", "Água, luz e internet", "Água, luz e internet", 450, 6),
    ("Dental Suprimentos", "Material odontológico", "Material odontológico", 1350, None),
    ("Laboratório Sorriso", "Prótese", "Laboratório de prótese", 980, None),
    ("Contabilidade Ágil", "Honorários contábeis", "Outras despesas", 600, 6),
]


def _simular_despesas(clinica, sorteio, contas, usuario):
    """Monthly bills from 2 months ago to 3 months ahead and a few purchases (mostly paid)."""
    from decimal import Decimal

    from apps.financeiro import servicos
    from apps.financeiro.models import Categoria, Lancamento

    categorias = {
        c.nome: c for c in Categoria.objects.filter(clinica=clinica, tipo=Categoria.Tipo.DESPESA)
    }
    hoje = timezone.localdate()
    inicio = servicos.somar_meses(hoje.replace(day=10), -2)
    criadas = 0
    for fornecedor, descricao, categoria, valor, meses in DESPESAS_SIMULADAS:
        if categoria not in categorias:
            continue
        parcelas = meses or sorteio.choice([1, 2, 3])
        valor = Decimal(valor)
        lancamento = servicos.criar_lancamento(
            clinica=clinica,
            tipo=Lancamento.Tipo.PAGAR,
            pessoa=fornecedor,
            descricao=descricao,
            categoria=categorias[categoria],
            valor_total=valor * parcelas if meses else valor,
            data=inicio,
            parcelas=parcelas,
            primeiro_vencimento=inicio if meses else hoje - datetime.timedelta(days=20),
            usuario=usuario,
        )
        for parcela in lancamento.parcelas.all():
            if parcela.vencimento <= hoje and sorteio.random() < 0.9:
                servicos.receber(
                    parcela,
                    usuario=usuario,
                    valor=parcela.valor,
                    data=parcela.vencimento,
                    forma=sorteio.choice(["pix", "boleto", "transferencia"]),
                    conta=sorteio.choice(contas),
                )
        criadas += 1
    return criadas


# Example price list for a test clinic without one: (name, price).
PROCEDIMENTOS_EXEMPLO = [
    ("Consulta de avaliação", 150),
    ("Limpeza (profilaxia)", 200),
    ("Restauração em resina", 250),
    ("Extração simples", 300),
    ("Tratamento de canal", 1200),
    ("Clareamento", 900),
    ("Coroa de porcelana", 1800),
    ("Aplicação de flúor", 80),
]


def simular_orcamentos(clinica, sorteio, quantidade=20, usuario=None):
    """Fake estimates of the last 60 days: some approved (they become receivables), some
    refused, the rest open. Creates an example price list if the clinic has none."""
    from decimal import Decimal

    from apps.financeiro.models import Categoria
    from apps.odontologia.dentes import DENTES_PERMANENTES
    from apps.orcamentos import servicos
    from apps.orcamentos.models import (
        ItemOrcamento,
        Orcamento,
        Procedimento,
    )

    tratamento = Categoria.objects.filter(clinica=clinica, nome="Tratamento").first()
    if not Procedimento.objects.filter(clinica=clinica).exists():
        Procedimento.objects.bulk_create(
            Procedimento(clinica=clinica, nome=nome, valor=Decimal(valor), categoria=tratamento)
            for nome, valor in PROCEDIMENTOS_EXEMPLO
        )
    procedimentos = list(Procedimento.objects.filter(clinica=clinica, ativo=True))
    pacientes = _pacientes(clinica)
    profissionais = list(Profissional.objects.filter(clinica=clinica, ativo=True))
    categoria = (
        tratamento or Categoria.objects.filter(clinica=clinica, tipo=Categoria.Tipo.RECEITA).first()
    )
    if not (procedimentos and pacientes and categoria):
        return 0
    dentes = [d for linha in DENTES_PERMANENTES for d in linha]
    hoje = timezone.localdate()
    for _ in range(quantidade):
        data = hoje - datetime.timedelta(days=sorteio.randint(0, 60))
        orcamento = Orcamento.objects.create(
            clinica=clinica,
            paciente=sorteio.choice(pacientes),
            profissional=sorteio.choice(profissionais) if profissionais else None,
            data=data,
            validade=data + datetime.timedelta(days=30),
            criado_por=usuario,
        )
        for procedimento in sorteio.sample(procedimentos, sorteio.randint(1, 3)):
            escolhidos = sorted(sorteio.sample(dentes, sorteio.randint(0, 3)))
            ItemOrcamento.objects.create(
                clinica=clinica,
                orcamento=orcamento,
                procedimento=procedimento,
                descricao=procedimento.nome,
                dentes=",".join(str(d) for d in escolhidos),
                quantidade=max(len(escolhidos), 1),
                valor_unitario=procedimento.valor,
            )
        sorte = sorteio.random()
        if sorte < 0.4:
            servicos.aprovar(
                orcamento,
                parcelas=sorteio.choice([1, 2, 3, 4]),
                primeiro_vencimento=data + datetime.timedelta(days=7),
                categoria=categoria,
                usuario=usuario,
            )
        elif sorte < 0.6:
            servicos.recusar(orcamento, usuario=usuario)
    return quantidade


def simular_comissoes(clinica, sorteio, usuario=None):
    """Give practitioners without one a commission percentage and pay out what each had
    pending up to the end of last month (test clinics only). Returns how many were paid."""
    from decimal import Decimal

    from apps.financeiro import comissoes
    from apps.financeiro.models import Categoria

    categoria = Categoria.objects.filter(
        clinica=clinica, tipo=Categoria.Tipo.DESPESA, nome="Comissões"
    ).first()
    if categoria is None:
        return 0
    fim_do_mes_passado = timezone.localdate().replace(day=1) - datetime.timedelta(days=1)
    pagas = 0
    for profissional in Profissional.objects.filter(clinica=clinica, ativo=True):
        if not profissional.comissao_percentual:
            profissional.comissao_percentual = Decimal(sorteio.choice([30, 35, 40]))
            profissional.save(update_fields=["comissao_percentual"])
        # Runs without isolation (like the command); the practitioner pins the clinic.
        if comissoes.pendente(profissional, fim_do_mes_passado)["valor"] > 0:
            comissoes.pagar(
                profissional,
                ate=fim_do_mes_passado,
                vencimento=fim_do_mes_passado + datetime.timedelta(days=5),
                categoria=categoria,
                usuario=usuario,
            )
            pagas += 1
    return pagas
