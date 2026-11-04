"""Import of the legacy Odonto System dump. Uses a small made-up dump (no real data)."""

import datetime
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import usar_clinica
from apps.core.models import Clinic
from apps.finance import services
from apps.finance.models import Category, Entry, Supplier
from apps.health_plans.models import HealthPlan, MemberCard
from apps.legacy.anonymization import RECHAMADAS
from apps.legacy.dump import DumpInvalido, ler_tabelas
from apps.legacy.importer import ImportacaoRecusada, _documento, importar
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule.models import Appointment, AppointmentType
from apps.staff.models import Employee, Payroll, Salary

HOJE = datetime.date(2026, 10, 27)

PESSOAS_COLUNAS = (
    "`id`, `tipo_pessoa`, `nome`, `profissao`, `razao_social`, `rg`, `rg_obs`, `cpf_cnpj`, "
    "`insc_est`, `sexo`, `data_nasc`, `estado_civil`, `responsavel`, `fone_res`, `fone_com`, "
    "`fone_cel`, `fone_fax`, `email`, `homepage`, `msn`, `id_cidade`, `id_bairrocomunidade`, "
    "`id_logradouro`, `endereco_num`, `endereco_compl`, `cep`, `saldo`, `id_banco`, `agencia`, "
    "`conta`, `obs`, `ativo`, `data_pgto`, `data_cadast`"
)

DUMP = f"""
-- phpMyAdmin SQL Dump (made-up data)
INSERT INTO `uf` (`id`, `nome`, `sigla`) VALUES (42, 'Santa Catarina', 'SC');
INSERT INTO `cidade` (`id`, `id_uf`, `microregiao`, `cidade`, `distrito`) VALUES
(1, '42', NULL, 'Florianopolis', 'Centro'),
(2, '42', NULL, 'Cidade Que Nao Existe', NULL);
INSERT INTO `tipo_endereco` (`id`, `nome`) VALUES (1, 'OUTROS'), (5, 'AVENIDA');
INSERT INTO `bairrocomunidade` (`id`, `id_cidade`, `nome`, `tipo`) VALUES (3, 1, 'Trindade', 'B');
INSERT INTO `logradouro` (`id`, `id_bairrocomunidade`, `nome`, `id_tipo_endereco`) VALUES
(7, 3, 'Beira-Mar', 5);
INSERT INTO `pessoas_estado_civil` (`id`, `nome`) VALUES
(1, '<< selecione >>'), (2, 'SOLTEIRO'), (6, 'VIÚVO');
INSERT INTO `dentistas` (`id`, `nome`) VALUES (1, 'Dr Teste'), (3, '_Consultório 2');
INSERT INTO `agenda_cor` (`id`, `nome`, `cor`) VALUES
(2, 'Cirurgia', '#f7a5a5'), (3, 'Dentistica', '#f6f7a5'), (11, 'Cor Nova', 'vermelho');
INSERT INTO `pessoas` ({PESSOAS_COLUNAS}) VALUES
(10, 'F', 'JoÃ£o d\\'Ávila', 'Pedreiro', '', '123', '', '1234567890', '', 'M', '1980-02-03',
 2, '', '4830001111', '', '99998888', '', 'joao@example.com', '', '', 1, 3, 7, '100', 'apto 1',
 '88040000', 150.5, 1, '', '', 'Alergia a dipirona', 'S', '2019-05-06', '2012-04-05'),
(11, 'F', 'Ana Duplicada', '', '', '', '', '012.345.678-90', '', '1', '0000-00-00',
 6, '', '', '', '', '3333', 'email-invalido', 'www.ana.example', '', 2, 0, 0, '', '',
 '880', 0, 1, '', '', '', 'N', '0000-00-00', '0000-00-00'),
(12, 'F', 'Bia CPF Errado', '', '', '', '', '11111111112', '', 'F', '1990-01-01',
 0, '', '', '', '', '', '', '', '', 0, 0, 0, '', '', '', 0, 1, '', '', '', 'S',
 '0000-00-00', '2015-01-01'),
(13, 'J', 'Empresa Teste', '', 'Empresa Teste Ltda', '', '', '11222333000181', '123', '',
 '0000-00-00',
 0, '', '', '4830002222', '', '', '', '', '', 0, 0, 0, '', '', '', 0, 1, '', '', '', 'S',
 '0000-00-00', '2016-01-01');
INSERT INTO `agendax` (`id`, `id_dentista`, `id_cor`, `data_marcar`, `hora_inicial`,
`hora_final`, `descricao`) VALUES
(1, 1, 2, '2019-10-01', '08:00:00', '09:00:00', 'Fulano - extração'),
(2, 1, 3, '2019-10-01', '09:00:00', '09:00:00', 'Término igual ao início'),
(3, 0, 0, '2019-10-01', '10:00:00', '10:30:00', 'Sem dentista'),
(4, 1, 2, '2019-10-01', '08:30:00', '09:30:00', 'Sobreposto'),
(5, 3, 11, '2019-10-02', '14:00:00', '14:30:00', ''),
(6, 3, 2, '2019-10-03', '19:30:00', '21:00:00', 'Até tarde');
INSERT INTO `agenda` (`id`, `id_pessoa`, `is_rechamada`, `inicio`, `fim`, `descricao`,
`data_marcar`) VALUES
(1, 10, 1, '00:00:00', '00:00:00', 'Revisão semestral', '2015-01-06'),
(2, 13, 1, '00:00:00', '00:00:00', 'Retorno', '2027-01-10'),
(3, 999, 1, '00:00:00', '00:00:00', 'Pessoa apagada', '2014-01-01');
INSERT INTO `sist_usuarios` (`id`, `login`) VALUES (1, 'nao-importar');
"""


# --- Dump reader -------------------------------------------------------------------


def test_le_valores_com_escapes_nulos_e_numeros():
    tabelas = ler_tabelas(
        "INSERT INTO `t` (`a`, `b`, `c`, `d`) VALUES "
        "(1, 'it''s \\'ok\\'\\n(x), y;', NULL, 2.5), (-3, '', 'z', 0);"
    )
    assert tabelas["t"] == [
        {"a": 1, "b": "it's 'ok'\n(x), y;", "c": None, "d": 2.5},
        {"a": -3, "b": "", "c": "z", "d": 0},
    ]


def test_filtra_tabelas():
    tabelas = ler_tabelas(DUMP, {"dentistas"})
    assert list(tabelas) == ["dentistas"]


@pytest.mark.parametrize(
    "texto",
    [
        "INSERT INTO `t` (`a`) VALUES ('sem fim",
        "INSERT INTO `t` (`a`, `b`) VALUES (1);",
        "INSERT INTO `t` VALUES (1);",
        "INSERT INTO `t` (`a`) VALUES (abc);",
    ],
)
def test_dump_invalido(texto):
    with pytest.raises(DumpInvalido):
        ler_tabelas(texto)


# --- Import ------------------------------------------------------------------------


@pytest.fixture
def importado(db):
    relatorio = importar(DUMP, "Clínica Importada", hoje=HOJE)
    return relatorio, relatorio.clinic


def dados(clinic, modelo, **filtro):
    with usar_clinica(clinic):
        return list(modelo.objects.filter(**filtro).order_by("pk"))


def test_relatorio(importado):
    relatorio, _ = importado
    assert (relatorio.profissionais, relatorio.pacientes) == (2, 4)
    assert (relatorio.agendamentos, relatorio.rechamadas, relatorio.tipos_criados) == (4, 2, 1)
    avisos = relatorio.avisos
    assert avisos["Agendamento sem profissional, tipo ou data válidos (não importado)"] == 1
    assert avisos["Agendamento sobreposto a outro do mesmo profissional (não importado)"] == 1
    assert avisos["Agendamento com término antes do início (corrigido para 30 min)"] == 1
    assert avisos["Rechamada de paciente inexistente ou sem data (não importada)"] == 1


def test_horario_da_agenda_cobre_os_atendimentos(importado):
    relatorio, clinic = importado
    clinic.refresh_from_db()
    assert (clinic.agenda_inicio, clinic.agenda_fim) == (datetime.time(7, 30), datetime.time(21))
    assert any(aviso.startswith("Horário da agenda ampliado") for aviso in relatorio.avisos)


def test_profissionais_e_tipos(importado):
    _, clinic = importado
    assert [p.name for p in dados(clinic, Practitioner)] == ["Dr Teste", "Consultório 2"]
    nomes = {t.name for t in dados(clinic, AppointmentType)}
    assert "Dentística" in nomes  # matched without accents, not duplicated
    assert "Dentistica" not in nomes
    nova = dados(clinic, AppointmentType, name="Cor Nova")[0]
    assert nova.color == "#0d6efd"  # invalid legacy color replaced


def test_paciente_completo(importado):
    _, clinic = importado
    joao = dados(clinic, Patient, name="João d'Ávila")[0]  # Latin-1 mojibake fixed
    assert joao.tax_id == "01234567890"  # leading zero restored
    assert (joao.sexo, joao.data_nascimento) == ("M", datetime.date(1980, 2, 3))
    assert joao.estado_civil.name == "Solteiro(a)"
    assert joao.city.name == "Florianópolis" and joao.state.sigla == "SC"
    assert (joao.neighborhood, joao.logradouro, joao.number) == (
        "Trindade",
        "Avenida Beira-Mar",
        "100",
    )
    assert (joao.telefone_residencial, joao.telefone_celular) == ("4830001111", "99998888")
    assert joao.notes.startswith("Alergia a dipirona\n\n[Sistema antigo]")
    for trecho in [
        "Código no sistema antigo: 10",
        "Saldo: R$ 150,50",
        "Último pagamento: 06/05/2019",
    ]:
        assert trecho in joao.notes
    assert timezone.localtime(joao.created_at).date() == datetime.date(2012, 4, 5)


def test_dados_que_nao_cabem_vao_para_as_observacoes(importado):
    _, clinic = importado
    ana = dados(clinic, Patient, name="Ana Duplicada")[0]
    # Same CPF as João after restoring the leading zero: kept only in the notes.
    assert ana.tax_id == ""
    assert "CPF/CNPJ no sistema antigo: 012.345.678-90" in ana.notes
    assert (ana.sexo, ana.data_nascimento, ana.estado_civil.name) == ("", None, "Viúvo(a)")
    assert ana.email == "" and "E-mail no sistema antigo: email-invalido" in ana.notes
    assert ana.cep == "" and "CEP no sistema antigo: 880" in ana.notes
    assert ana.city is None and "Cidade no sistema antigo: Cidade Que Nao Existe/SC" in ana.notes
    assert "Fax: 3333" in ana.notes and "Site: www.ana.example" in ana.notes
    assert not ana.active

    bia = dados(clinic, Patient, name="Bia CPF Errado")[0]
    assert bia.tax_id == "" and "CPF/CNPJ no sistema antigo: 11111111112" in bia.notes

    empresa = dados(clinic, Patient, name="Empresa Teste")[0]
    assert (empresa.kind, empresa.tax_id) == ("PJ", "11222333000181")
    assert (empresa.legal_name, empresa.inscricao_estadual) == ("Empresa Teste Ltda", "123")


@pytest.mark.parametrize(
    ("bruto", "kind", "esperado"),
    [
        ("012.345.678-90", Patient.Tipo.FISICA, ("01234567890", None)),
        ("12345678-90", Patient.Tipo.FISICA, ("01234567890", None)),
        # cpf_valido ignores letters: a CPF with junk is not taken as valid.
        ("012.345.678-90X", Patient.Tipo.FISICA, ("", "012.345.678-90X")),
        ("isento", Patient.Tipo.FISICA, ("", "isento")),
        ("", Patient.Tipo.FISICA, ("", None)),
        ("1222333000128", Patient.Tipo.JURIDICA, ("01222333000128", None)),
    ],
)
def test_documento(bruto, kind, esperado):
    assert _documento(bruto, kind) == esperado


def test_agenda_e_rechamadas(importado):
    _, clinic = importado
    agendamentos = dados(clinic, Appointment)
    assert [a.description.splitlines()[0] for a in agendamentos] == [
        "Fulano - extração",
        "Término igual ao início",
        "Cor Nova",  # no legacy description: the type name, so the slot stays editable
        "Até tarde",
    ]
    corrigido = agendamentos[1]
    assert corrigido.end - corrigido.start == datetime.timedelta(minutes=30)
    assert all(a.patient is None for a in agendamentos)
    assert timezone.localtime(agendamentos[0].start).hour == 8

    rechamadas = dados(clinic, Recall)
    assert [(r.patient.name, r.concluida) for r in rechamadas] == [
        ("João d'Ávila", True),  # past recall: considered handled
        ("Empresa Teste", False),
    ]


def test_registro_na_auditoria_e_sem_usuarios(importado, django_user_model):
    _, clinic = importado
    record = AuditEntry.objects.get(clinic=clinic, objeto_descricao__startswith="Importação")
    assert "4 pacientes, 4 agendamentos, 2 rechamadas" in record.objeto_descricao
    assert not django_user_model.objects.exists()


def test_nao_importa_duas_vezes_na_mesma_clinica(importado):
    with pytest.raises(ImportacaoRecusada):
        importar(DUMP, "Clínica Importada", hoje=HOJE)
    _, clinic = importado
    assert len(dados(clinic, Patient)) == 4


def test_falha_nao_deixa_nada_pela_metade(db, monkeypatch):
    from apps.legacy import importer

    def quebrar(self, pacientes):
        raise RuntimeError("falha no meio")

    monkeypatch.setattr(importer._Importador, "_rechamadas", quebrar)
    with pytest.raises(RuntimeError):
        importar(DUMP, "Clínica Importada", hoje=HOJE)
    assert not Clinic.objects.filter(name="Clínica Importada").exists()


def test_comando(db, tmp_path, capsys):
    file = tmp_path / "dump.sql"
    file.write_text(DUMP, encoding="utf-8")
    call_command("import_legacy", str(file), clinic="Pelo Comando")
    saida = capsys.readouterr().out
    assert "Pacientes: 4" in saida and "Avisos:" in saida
    with pytest.raises(CommandError):
        call_command("import_legacy", str(file), clinic="Pelo Comando")
    with pytest.raises(CommandError):
        call_command("import_legacy", str(tmp_path / "nao-existe.sql"), clinic="X")


# --- Anonymization -----------------------------------------------------------------


def test_anonimizacao_troca_os_dados_pessoais_e_mantem_a_estrutura(importado):
    _, clinic = importado
    antes = {
        "pacientes": dados(clinic, Patient),
        "agendamentos": dados(clinic, Appointment),
        "profissionais": dados(clinic, Practitioner),
    }
    with pytest.raises(CommandError):
        call_command("anonymize_clinic", clinic=clinic.name)
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)

    pacientes = dados(clinic, Patient)
    assert [p.pk for p in pacientes] == [p.pk for p in antes["pacientes"]]
    originais = [
        "Ávila",
        "Duplicada",
        "Bia CPF",
        "Empresa Teste",
        "01234567890",
        "11222333000181",
        "4830001111",
        "joao@example.com",
        "Beira-Mar",
        "Trindade",
        "Sistema antigo",
    ]
    texto = str([vars(p) for p in pacientes])
    assert not [trecho for trecho in originais if trecho in texto]
    for velho, novo in zip(antes["pacientes"], pacientes, strict=True):
        assert (novo.kind, novo.sexo, novo.active, novo.city_id) == (
            velho.kind,
            velho.sexo,
            velho.active,
            velho.city_id,
        )
        assert bool(novo.tax_id) == bool(velho.tax_id)
        assert bool(novo.telefone_residencial) == bool(velho.telefone_residencial)
        if velho.data_nascimento:
            assert abs((novo.data_nascimento - velho.data_nascimento).days) <= 180
    joao = next(p for p in pacientes if p.pk == antes["pacientes"][0].pk)
    assert joao.telefone_residencial.startswith("48")  # area code kept
    assert len(joao.tax_id) == 11

    agendamentos = dados(clinic, Appointment)
    assert [(a.start, a.end, a.practitioner_id) for a in agendamentos] == [
        (a.start, a.end, a.practitioner_id) for a in antes["agendamentos"]
    ]
    descricoes = [a.description for a in agendamentos]
    assert "Cor Nova" in descricoes  # blocked slot: no personal data, kept
    assert not [d for d in descricoes if "Fulano" in d or "Até tarde" in d]
    assert {r.description for r in dados(clinic, Recall)} <= set(RECHAMADAS)
    nomes = [p.name for p in dados(clinic, Practitioner)]
    assert "Dr Teste" not in nomes and len(nomes) == len(antes["profissionais"])

    # The audit no longer holds the original values; the anonymization is recorded.
    registros = AuditEntry.objects.filter(clinic=clinic)
    assert not registros.filter(modelo="Paciente").exists()
    assert not registros.filter(objeto_descricao__startswith="Importação").exists()
    assert registros.filter(objeto_descricao__startswith="Dados anonimizados: 4 pacientes").exists()


def test_anonimizar_clinica_inexistente(db):
    with pytest.raises(CommandError, match="não encontrada"):
        call_command("anonymize_clinic", clinic="Não existe", confirmar=True)


def test_anonimizacao_dos_fornecedores(importado):
    _, clinic = importado
    with usar_clinica(clinic):
        pessoa = Supplier.objects.create(
            kind=Supplier.Tipo.FISICA,
            name="Fulana Fornecedora",
            tax_id="52998224725",
            phone="4833334444",
            email="fulana@example.com",
            notes="Indicada pela Fulana",
        )
        empresa = Supplier.objects.create(name="Dental Fictícia", whatsapp="48999990000")
        category = Category.objects.filter(kind=Category.Tipo.DESPESA).first()
        for fornecedor in (pessoa, empresa):
            services.criar_lancamento(
                clinic=clinic,
                kind=Entry.Tipo.PAGAR,
                fornecedor=fornecedor,
                pessoa=fornecedor.name,
                description="Compra",
                category=category,
                valor_total=Decimal("10"),
                parcelas=1,
                primeiro_vencimento=HOJE,
                user=None,
            )
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)

    pessoa, empresa = dados(clinic, Supplier)
    assert "Fulana" not in str(vars(pessoa))
    assert (pessoa.tax_id, len(pessoa.phone)) == ("", 10)
    assert pessoa.email.endswith("@example.com")
    assert empresa.name == "Dental Fictícia"  # a company name is not personal data
    assert len(empresa.whatsapp) == 11 and empresa.whatsapp != "48999990000"
    # Payables keep showing their supplier's (new) name.
    for entry in dados(clinic, Entry, kind=Entry.Tipo.PAGAR):
        assert entry.pessoa == entry.fornecedor.name


def test_anonimizacao_das_carteirinhas(importado):
    _, clinic = importado
    with usar_clinica(clinic):
        convenio = HealthPlan.objects.create(name="Saúde Exemplo")
        MemberCard.objects.create(
            patient=Patient.objects.first(),
            convenio=convenio,
            plano="Básico",
            number="98765",
            titular="Fulano Titular",
        )
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)
    (carteirinha,) = dados(clinic, MemberCard)
    assert carteirinha.number != "98765" and "Fulano" not in carteirinha.titular
    assert carteirinha.titular and (carteirinha.convenio, carteirinha.plano) == (convenio, "Básico")


def test_anonimizacao_dos_funcionarios(importado):
    _, clinic = importado
    with usar_clinica(clinic):
        funcionaria = Employee.objects.create(
            name="Fulana Funcionária", cpf="52998224725", phone="4833334444"
        )
        Salary.objects.create(employee=funcionaria, amount=Decimal("2000"), desde=HOJE)
        folha = Payroll.objects.create(
            employee=funcionaria,
            competencia=HOJE.replace(day=1),
            salario=Decimal("2000"),
            note="Atestado da Fulana",
        )
        category = Category.objects.filter(kind=Category.Tipo.DESPESA).first()
        folha.entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.PAGAR,
            pessoa=funcionaria.name,
            description="Salário",
            category=category,
            valor_total=Decimal("2000"),
            parcelas=1,
            primeiro_vencimento=HOJE,
            user=None,
        )
        folha.save()
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)
    (funcionaria,) = dados(clinic, Employee)
    (folha,) = dados(clinic, Payroll)
    assert "Fulana" not in funcionaria.name and funcionaria.cpf == ""
    assert len(funcionaria.phone) == 10 and folha.note == ""
    with usar_clinica(clinic):
        assert Entry.objects.get(pk=folha.entry_id).pessoa == funcionaria.name
        assert funcionaria.salario_em(HOJE) == Decimal("2000")
