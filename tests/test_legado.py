"""Import of the legacy Odonto System dump. Uses a small made-up dump (no real data)."""

import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.auditoria.models import RegistroAuditoria
from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica
from apps.legado.dump import DumpInvalido, ler_tabelas
from apps.legado.importacao import ImportacaoRecusada, _documento, importar
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

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
    return relatorio, relatorio.clinica


def dados(clinica, modelo, **filtro):
    with usar_clinica(clinica):
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
    relatorio, clinica = importado
    clinica.refresh_from_db()
    assert (clinica.agenda_inicio, clinica.agenda_fim) == (datetime.time(7, 30), datetime.time(21))
    assert any(aviso.startswith("Horário da agenda ampliado") for aviso in relatorio.avisos)


def test_profissionais_e_tipos(importado):
    _, clinica = importado
    assert [p.nome for p in dados(clinica, Profissional)] == ["Dr Teste", "Consultório 2"]
    nomes = {t.nome for t in dados(clinica, TipoAtendimento)}
    assert "Dentística" in nomes  # matched without accents, not duplicated
    assert "Dentistica" not in nomes
    nova = dados(clinica, TipoAtendimento, nome="Cor Nova")[0]
    assert nova.cor == "#0d6efd"  # invalid legacy color replaced


def test_paciente_completo(importado):
    _, clinica = importado
    joao = dados(clinica, Paciente, nome="João d'Ávila")[0]  # Latin-1 mojibake fixed
    assert joao.cpf_cnpj == "01234567890"  # leading zero restored
    assert (joao.sexo, joao.data_nascimento) == ("M", datetime.date(1980, 2, 3))
    assert joao.estado_civil.nome == "Solteiro(a)"
    assert joao.cidade.nome == "Florianópolis" and joao.uf.sigla == "SC"
    assert (joao.bairro, joao.logradouro, joao.numero) == ("Trindade", "Avenida Beira-Mar", "100")
    assert (joao.telefone_residencial, joao.telefone_celular) == ("4830001111", "99998888")
    assert joao.observacoes.startswith("Alergia a dipirona\n\n[Sistema antigo]")
    for trecho in [
        "Código no sistema antigo: 10",
        "Saldo: R$ 150,50",
        "Último pagamento: 06/05/2019",
    ]:
        assert trecho in joao.observacoes
    assert timezone.localtime(joao.criado_em).date() == datetime.date(2012, 4, 5)


def test_dados_que_nao_cabem_vao_para_as_observacoes(importado):
    _, clinica = importado
    ana = dados(clinica, Paciente, nome="Ana Duplicada")[0]
    # Same CPF as João after restoring the leading zero: kept only in the notes.
    assert ana.cpf_cnpj == ""
    assert "CPF/CNPJ no sistema antigo: 012.345.678-90" in ana.observacoes
    assert (ana.sexo, ana.data_nascimento, ana.estado_civil.nome) == ("", None, "Viúvo(a)")
    assert ana.email == "" and "E-mail no sistema antigo: email-invalido" in ana.observacoes
    assert ana.cep == "" and "CEP no sistema antigo: 880" in ana.observacoes
    assert (
        ana.cidade is None
        and "Cidade no sistema antigo: Cidade Que Nao Existe/SC" in ana.observacoes
    )
    assert "Fax: 3333" in ana.observacoes and "Site: www.ana.example" in ana.observacoes
    assert not ana.ativo

    bia = dados(clinica, Paciente, nome="Bia CPF Errado")[0]
    assert bia.cpf_cnpj == "" and "CPF/CNPJ no sistema antigo: 11111111112" in bia.observacoes

    empresa = dados(clinica, Paciente, nome="Empresa Teste")[0]
    assert (empresa.tipo, empresa.cpf_cnpj) == ("PJ", "11222333000181")
    assert (empresa.razao_social, empresa.inscricao_estadual) == ("Empresa Teste Ltda", "123")


@pytest.mark.parametrize(
    ("bruto", "tipo", "esperado"),
    [
        ("012.345.678-90", Paciente.Tipo.FISICA, ("01234567890", None)),
        ("12345678-90", Paciente.Tipo.FISICA, ("01234567890", None)),
        # cpf_valido ignores letters: a CPF with junk is not taken as valid.
        ("012.345.678-90X", Paciente.Tipo.FISICA, ("", "012.345.678-90X")),
        ("isento", Paciente.Tipo.FISICA, ("", "isento")),
        ("", Paciente.Tipo.FISICA, ("", None)),
        ("1222333000128", Paciente.Tipo.JURIDICA, ("01222333000128", None)),
    ],
)
def test_documento(bruto, tipo, esperado):
    assert _documento(bruto, tipo) == esperado


def test_agenda_e_rechamadas(importado):
    _, clinica = importado
    agendamentos = dados(clinica, Agendamento)
    assert [a.descricao.splitlines()[0] for a in agendamentos] == [
        "Fulano - extração",
        "Término igual ao início",
        "Cor Nova",  # no legacy description: the type name, so the slot stays editable
        "Até tarde",
    ]
    corrigido = agendamentos[1]
    assert corrigido.fim - corrigido.inicio == datetime.timedelta(minutes=30)
    assert all(a.paciente is None for a in agendamentos)
    assert timezone.localtime(agendamentos[0].inicio).hour == 8

    rechamadas = dados(clinica, Rechamada)
    assert [(r.paciente.nome, r.concluida) for r in rechamadas] == [
        ("João d'Ávila", True),  # past recall: considered handled
        ("Empresa Teste", False),
    ]


def test_registro_na_auditoria_e_sem_usuarios(importado, django_user_model):
    _, clinica = importado
    registro = RegistroAuditoria.objects.get(
        clinica=clinica, objeto_descricao__startswith="Importação"
    )
    assert "4 pacientes, 4 agendamentos, 2 rechamadas" in registro.objeto_descricao
    assert not django_user_model.objects.exists()


def test_nao_importa_duas_vezes_na_mesma_clinica(importado):
    with pytest.raises(ImportacaoRecusada):
        importar(DUMP, "Clínica Importada", hoje=HOJE)
    _, clinica = importado
    assert len(dados(clinica, Paciente)) == 4


def test_falha_nao_deixa_nada_pela_metade(db, monkeypatch):
    from apps.legado import importacao

    def quebrar(self, pacientes):
        raise RuntimeError("falha no meio")

    monkeypatch.setattr(importacao._Importador, "_rechamadas", quebrar)
    with pytest.raises(RuntimeError):
        importar(DUMP, "Clínica Importada", hoje=HOJE)
    assert not Clinica.objects.filter(nome="Clínica Importada").exists()


def test_comando(db, tmp_path, capsys):
    arquivo = tmp_path / "dump.sql"
    arquivo.write_text(DUMP, encoding="utf-8")
    call_command("importar_legado", str(arquivo), clinica="Pelo Comando")
    saida = capsys.readouterr().out
    assert "Pacientes: 4" in saida and "Avisos:" in saida
    with pytest.raises(CommandError):
        call_command("importar_legado", str(arquivo), clinica="Pelo Comando")
    with pytest.raises(CommandError):
        call_command("importar_legado", str(tmp_path / "nao-existe.sql"), clinica="X")
