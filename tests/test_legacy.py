"""Import of the legacy Odonto System dump. Uses a small made-up dump (no real data)."""

import datetime
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import use_clinic
from apps.core.models import Clinic
from apps.finance import services
from apps.finance.models import Category, Entry, Supplier
from apps.health_plans.models import HealthPlan, MemberCard
from apps.legacy.anonymization import RECALLS
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
    tables = ler_tabelas(
        "INSERT INTO `t` (`a`, `b`, `c`, `d`) VALUES "
        "(1, 'it''s \\'ok\\'\\n(x), y;', NULL, 2.5), (-3, '', 'z', 0);"
    )
    assert tables["t"] == [
        {"a": 1, "b": "it's 'ok'\n(x), y;", "c": None, "d": 2.5},
        {"a": -3, "b": "", "c": "z", "d": 0},
    ]


def test_filtra_tabelas():
    tables = ler_tabelas(DUMP, {"dentistas"})
    assert list(tables) == ["dentistas"]


@pytest.mark.parametrize(
    "text",
    [
        "INSERT INTO `t` (`a`) VALUES ('sem fim",
        "INSERT INTO `t` (`a`, `b`) VALUES (1);",
        "INSERT INTO `t` VALUES (1);",
        "INSERT INTO `t` (`a`) VALUES (abc);",
    ],
)
def test_dump_invalido(text):
    with pytest.raises(DumpInvalido):
        ler_tabelas(text)


# --- Import ------------------------------------------------------------------------


@pytest.fixture
def importado(db):
    relatorio = importar(DUMP, "Clínica Importada", today=HOJE)
    return relatorio, relatorio.clinic


def data(clinic, modelo, **filtro):
    with use_clinic(clinic):
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
    assert (clinic.schedule_start, clinic.schedule_end) == (datetime.time(7, 30), datetime.time(21))
    assert any(warning.startswith("Horário da agenda ampliado") for warning in relatorio.avisos)


def test_profissionais_e_tipos(importado):
    _, clinic = importado
    assert [p.name for p in data(clinic, Practitioner)] == ["Dr Teste", "Consultório 2"]
    nomes = {t.name for t in data(clinic, AppointmentType)}
    assert "Dentística" in nomes  # matched without accents, not duplicated
    assert "Dentistica" not in nomes
    nova = data(clinic, AppointmentType, name="Cor Nova")[0]
    assert nova.color == "#0d6efd"  # invalid legacy color replaced


def test_paciente_completo(importado):
    _, clinic = importado
    joao = data(clinic, Patient, name="João d'Ávila")[0]  # Latin-1 mojibake fixed
    assert joao.tax_id == "01234567890"  # leading zero restored
    assert (joao.sex, joao.birth_date) == ("M", datetime.date(1980, 2, 3))
    assert joao.marital_status.name == "Solteiro(a)"
    assert joao.city.name == "Florianópolis" and joao.state.abbreviation == "SC"
    assert (joao.neighborhood, joao.street, joao.number) == (
        "Trindade",
        "Avenida Beira-Mar",
        "100",
    )
    assert (joao.home_phone, joao.mobile_phone) == ("4830001111", "99998888")
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
    ana = data(clinic, Patient, name="Ana Duplicada")[0]
    # Same CPF as João after restoring the leading zero: kept only in the notes.
    assert ana.tax_id == ""
    assert "CPF/CNPJ no sistema antigo: 012.345.678-90" in ana.notes
    assert (ana.sex, ana.birth_date, ana.marital_status.name) == ("", None, "Viúvo(a)")
    assert ana.email == "" and "E-mail no sistema antigo: email-invalido" in ana.notes
    assert ana.postal_code == "" and "CEP no sistema antigo: 880" in ana.notes
    assert ana.city is None and "Cidade no sistema antigo: Cidade Que Nao Existe/SC" in ana.notes
    assert "Fax: 3333" in ana.notes and "Site: www.ana.example" in ana.notes
    assert not ana.active

    bia = data(clinic, Patient, name="Bia CPF Errado")[0]
    assert bia.tax_id == "" and "CPF/CNPJ no sistema antigo: 11111111112" in bia.notes

    empresa = data(clinic, Patient, name="Empresa Teste")[0]
    assert (empresa.kind, empresa.tax_id) == ("PJ", "11222333000181")
    assert (empresa.legal_name, empresa.state_registration) == ("Empresa Teste Ltda", "123")


@pytest.mark.parametrize(
    ("bruto", "kind", "esperado"),
    [
        ("012.345.678-90", Patient.Kind.INDIVIDUAL, ("01234567890", None)),
        ("12345678-90", Patient.Kind.INDIVIDUAL, ("01234567890", None)),
        # cpf_valido ignores letters: a CPF with junk is not taken as valid.
        ("012.345.678-90X", Patient.Kind.INDIVIDUAL, ("", "012.345.678-90X")),
        ("isento", Patient.Kind.INDIVIDUAL, ("", "isento")),
        ("", Patient.Kind.INDIVIDUAL, ("", None)),
        ("1222333000128", Patient.Kind.COMPANY, ("01222333000128", None)),
    ],
)
def test_documento(bruto, kind, esperado):
    assert _documento(bruto, kind) == esperado


def test_agenda_e_rechamadas(importado):
    _, clinic = importado
    agendamentos = data(clinic, Appointment)
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

    rechamadas = data(clinic, Recall)
    assert [(r.patient.name, r.done) for r in rechamadas] == [
        ("João d'Ávila", True),  # past recall: considered handled
        ("Empresa Teste", False),
    ]


def test_registro_na_auditoria_e_sem_usuarios(importado, django_user_model):
    _, clinic = importado
    record = AuditEntry.objects.get(clinic=clinic, object_repr__startswith="Importação")
    assert "4 pacientes, 4 agendamentos, 2 rechamadas" in record.object_repr
    assert not django_user_model.objects.exists()


def test_nao_importa_duas_vezes_na_mesma_clinica(importado):
    with pytest.raises(ImportacaoRecusada):
        importar(DUMP, "Clínica Importada", today=HOJE)
    _, clinic = importado
    assert len(data(clinic, Patient)) == 4


def test_falha_nao_deixa_nada_pela_metade(db, monkeypatch):
    from apps.legacy import importer

    def quebrar(self, pacientes):
        raise RuntimeError("falha no meio")

    monkeypatch.setattr(importer._Importador, "_recalls", quebrar)
    with pytest.raises(RuntimeError):
        importar(DUMP, "Clínica Importada", today=HOJE)
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
    before = {
        "pacientes": data(clinic, Patient),
        "agendamentos": data(clinic, Appointment),
        "profissionais": data(clinic, Practitioner),
    }
    with pytest.raises(CommandError):
        call_command("anonymize_clinic", clinic=clinic.name)
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)

    pacientes = data(clinic, Patient)
    assert [p.pk for p in pacientes] == [p.pk for p in before["pacientes"]]
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
    text = str([vars(p) for p in pacientes])
    assert not [trecho for trecho in originais if trecho in text]
    for velho, new in zip(before["pacientes"], pacientes, strict=True):
        assert (new.kind, new.sex, new.active, new.city_id) == (
            velho.kind,
            velho.sex,
            velho.active,
            velho.city_id,
        )
        assert bool(new.tax_id) == bool(velho.tax_id)
        assert bool(new.home_phone) == bool(velho.home_phone)
        if velho.birth_date:
            assert abs((new.birth_date - velho.birth_date).days) <= 180
    joao = next(p for p in pacientes if p.pk == before["pacientes"][0].pk)
    assert joao.home_phone.startswith("48")  # area code kept
    assert len(joao.tax_id) == 11

    agendamentos = data(clinic, Appointment)
    assert [(a.start, a.end, a.practitioner_id) for a in agendamentos] == [
        (a.start, a.end, a.practitioner_id) for a in before["agendamentos"]
    ]
    descricoes = [a.description for a in agendamentos]
    assert "Cor Nova" in descricoes  # blocked slot: no personal data, kept
    assert not [d for d in descricoes if "Fulano" in d or "Até tarde" in d]
    assert {r.description for r in data(clinic, Recall)} <= set(RECALLS)
    nomes = [p.name for p in data(clinic, Practitioner)]
    assert "Dr Teste" not in nomes and len(nomes) == len(before["profissionais"])

    # The audit no longer holds the original values; the anonymization is recorded.
    registros = AuditEntry.objects.filter(clinic=clinic)
    assert not registros.filter(model_name="Paciente").exists()
    assert not registros.filter(object_repr__startswith="Importação").exists()
    assert registros.filter(object_repr__startswith="Dados anonimizados: 4 pacientes").exists()


def test_anonimizar_clinica_inexistente(db):
    with pytest.raises(CommandError, match="não encontrada"):
        call_command("anonymize_clinic", clinic="Não existe", confirmar=True)


def test_anonimizacao_dos_fornecedores(importado):
    _, clinic = importado
    with use_clinic(clinic):
        pessoa = Supplier.objects.create(
            kind=Supplier.Kind.INDIVIDUAL,
            name="Fulana Fornecedora",
            tax_id="52998224725",
            phone="4833334444",
            email="fulana@example.com",
            notes="Indicada pela Fulana",
        )
        empresa = Supplier.objects.create(name="Dental Fictícia", whatsapp="48999990000")
        category = Category.objects.filter(kind=Category.Kind.EXPENSE).first()
        for supplier in (pessoa, empresa):
            services.create_entry(
                clinic=clinic,
                kind=Entry.Kind.PAYABLE,
                supplier=supplier,
                payer=supplier.name,
                description="Compra",
                category=category,
                total_amount=Decimal("10"),
                parcelas=1,
                primeiro_vencimento=HOJE,
                user=None,
            )
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)

    pessoa, empresa = data(clinic, Supplier)
    assert "Fulana" not in str(vars(pessoa))
    assert (pessoa.tax_id, len(pessoa.phone)) == ("", 10)
    assert pessoa.email.endswith("@example.com")
    assert empresa.name == "Dental Fictícia"  # a company name is not personal data
    assert len(empresa.whatsapp) == 11 and empresa.whatsapp != "48999990000"
    # Payables keep showing their supplier's (new) name.
    for entry in data(clinic, Entry, kind=Entry.Kind.PAYABLE):
        assert entry.payer == entry.supplier.name


def test_anonimizacao_das_carteirinhas(importado):
    _, clinic = importado
    with use_clinic(clinic):
        health_plan = HealthPlan.objects.create(name="Saúde Exemplo")
        MemberCard.objects.create(
            patient=Patient.objects.first(),
            health_plan=health_plan,
            plan="Básico",
            number="98765",
            holder="Fulano Titular",
        )
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)
    (carteirinha,) = data(clinic, MemberCard)
    assert carteirinha.number != "98765" and "Fulano" not in carteirinha.holder
    assert carteirinha.holder and (carteirinha.health_plan, carteirinha.plan) == (
        health_plan,
        "Básico",
    )


def test_anonimizacao_dos_funcionarios(importado):
    _, clinic = importado
    with use_clinic(clinic):
        funcionaria = Employee.objects.create(
            name="Fulana Funcionária", tax_id="52998224725", phone="4833334444"
        )
        Salary.objects.create(employee=funcionaria, amount=Decimal("2000"), effective_from=HOJE)
        folha = Payroll.objects.create(
            employee=funcionaria,
            period=HOJE.replace(day=1),
            salary=Decimal("2000"),
            note="Atestado da Fulana",
        )
        category = Category.objects.filter(kind=Category.Kind.EXPENSE).first()
        folha.entry = services.create_entry(
            clinic=clinic,
            kind=Entry.Kind.PAYABLE,
            payer=funcionaria.name,
            description="Salário",
            category=category,
            total_amount=Decimal("2000"),
            parcelas=1,
            primeiro_vencimento=HOJE,
            user=None,
        )
        folha.save()
    call_command("anonymize_clinic", clinic=clinic.name, confirmar=True)
    (funcionaria,) = data(clinic, Employee)
    (folha,) = data(clinic, Payroll)
    assert "Fulana" not in funcionaria.name and funcionaria.tax_id == ""
    assert len(funcionaria.phone) == 10 and folha.note == ""
    with use_clinic(clinic):
        assert Entry.objects.get(pk=folha.entry_id).payer == funcionaria.name
        assert funcionaria.salario_em(HOJE) == Decimal("2000")
