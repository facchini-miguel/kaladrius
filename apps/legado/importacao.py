"""Import of the legacy Odonto System data (MySQL dump) into a new clinic.

Mapping (the legacy system's notes are kept outside the repository, decision 073):
- dentistas → Profissional; agenda_cor → TipoAtendimento (matched by name);
- pessoas → Paciente; agendax → Agendamento (free text, no patient link, as in the legacy
  system); agenda (is_rechamada = 1) → Rechamada.
- Legacy-only data (finance fields, fax, legacy code, invalid documents...) is kept as
  text in the patient's notes, so nothing is lost.
- Users and groups are not imported: the clinic team is created in the new system.
"""

import datetime
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import registrar
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica
from apps.core.validadores import cnpj_valido, cpf_valido, normalizar_cnpj, somente_digitos
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada
from apps.referencias.models import UF, Cidade, EstadoCivil

from .dump import ler_tabelas

TABELAS = {
    "pessoas",
    "agendax",
    "agenda",
    "dentistas",
    "agenda_cor",
    "cidade",
    "uf",
    "bairrocomunidade",
    "logradouro",
    "tipo_endereco",
    "pessoas_estado_civil",
}
DURACAO_MINIMA = datetime.timedelta(minutes=30)


class ImportacaoRecusada(Exception):
    pass


@dataclass
class Relatorio:
    clinica: Clinica | None = None
    profissionais: int = 0
    tipos_criados: int = 0
    pacientes: int = 0
    agendamentos: int = 0
    rechamadas: int = 0
    avisos: Counter = field(default_factory=Counter)


# UTF-8 bytes of Portuguese letters read as Latin-1: "Ã£" instead of "ã", "Âº" instead of "º".
_MOJIBAKE = re.compile("[\u00c2\u00c3][\u0080-\u00bf]")


def _texto(valor):
    """Clean text: fixes UTF-8 read as Latin-1 ("JoÃ£o") and normalizes line breaks."""
    texto = "" if valor is None else str(valor)
    texto = _MOJIBAKE.sub(lambda m: m.group().encode("latin-1").decode("utf-8"), texto)
    return texto.replace("\r\n", "\n").replace("\r", "\n").strip()


def _chave(texto):
    """Comparison key: no accents, lowercase, only letters and digits."""
    sem_acentos = unicodedata.normalize("NFKD", _texto(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acentos.lower())


def _data(valor):
    try:
        return datetime.date.fromisoformat(str(valor))
    except ValueError:
        return None  # MySQL "0000-00-00"


def _hora(valor):
    try:
        return datetime.time.fromisoformat(str(valor))
    except ValueError:
        return None


def _email(valor):
    email = _texto(valor)
    if not email:
        return "", None
    try:
        validate_email(email)
    except ValidationError:
        return "", email
    return email, None


def _documento(bruto, tipo):
    """(valid document, None) or ("", original text) when it cannot be used."""
    original = _texto(bruto)
    documento = normalizar_cnpj(original)
    if not documento:
        return "", None
    so_digitos = documento.isascii() and documento.isdigit()
    if tipo == Paciente.Tipo.FISICA:
        if so_digitos and 8 <= len(documento) <= 11:
            documento = documento.zfill(11)  # leading zeros lost in the legacy system
        # cpf_valido ignores letters, so "123.456.789-09X" must be rejected here.
        return (documento, None) if so_digitos and cpf_valido(documento) else ("", original)
    if so_digitos and 12 <= len(documento) <= 14:
        documento = documento.zfill(14)
    return (documento, None) if cnpj_valido(documento) else ("", original)


def _cabe(valor, tamanho, rotulo, extras):
    """The value if it fits the field; otherwise it goes in full to the notes."""
    if len(valor) <= tamanho:
        return valor
    extras.append(f"{rotulo}: {valor}")
    return valor[:tamanho]


class _Importador:
    def __init__(self, tabelas, nome_clinica, hoje):
        self.t = tabelas
        self.nome_clinica = nome_clinica
        self.hoje = hoje
        self.relatorio = Relatorio()

    # --- Lookups -----------------------------------------------------------------

    def _cidades(self):
        """Legacy city id → (UF, IBGE city or None, legacy name)."""
        ufs_legado = {u["id"]: _texto(u["sigla"]).upper() for u in self.t.get("uf", [])}
        ufs = {uf.sigla: uf for uf in UF.objects.all()}
        ibge = defaultdict(dict)
        for cidade in Cidade.objects.select_related("uf"):
            ibge[cidade.uf.sigla][_chave(cidade.nome)] = cidade
        resultado = {}
        for linha in self.t.get("cidade", []):
            id_uf = str(linha["id_uf"] or "")
            sigla = ufs_legado.get(int(id_uf)) if id_uf.isdecimal() else None
            nome = _texto(linha["cidade"])
            resultado[linha["id"]] = (ufs.get(sigla), ibge[sigla].get(_chave(nome)), nome, sigla)
        return resultado

    def _estados_civis(self):
        novos = {_chave(e.nome)[:5]: e for e in EstadoCivil.objects.all()}
        return {
            linha["id"]: novos.get(_chave(linha["nome"])[:5])
            for linha in self.t.get("pessoas_estado_civil", [])
        }

    def _logradouros(self):
        tipos = {t["id"]: _texto(t["nome"]).title() for t in self.t.get("tipo_endereco", [])}
        resultado = {}
        for linha in self.t.get("logradouro", []):
            tipo = tipos.get(linha["id_tipo_endereco"], "")
            nome = _texto(linha["nome"])
            resultado[linha["id"]] = f"{tipo} {nome}" if tipo and tipo != "Outros" else nome
        return resultado

    # --- Steps -------------------------------------------------------------------

    def _clinica(self):
        clinica = Clinica.objects.filter(nome=self.nome_clinica).first()
        if clinica is not None and Paciente.objects.filter(clinica=clinica).exists():
            raise ImportacaoRecusada(
                f"A clínica “{self.nome_clinica}” já tem pacientes. A importação só é feita "
                "numa clínica nova ou vazia, para não duplicar dados."
            )
        if clinica is None:
            clinica = Clinica.objects.create(nome=self.nome_clinica)  # gets the default types
        self.relatorio.clinica = clinica
        return clinica

    def _profissionais(self, clinica):
        mapa = {}
        for linha in self.t.get("dentistas", []):
            nome = _texto(linha["nome"]).lstrip("_ ").strip() or f"Profissional {linha['id']}"
            mapa[linha["id"]] = Profissional.objects.create(clinica=clinica, nome=nome[:200])
        self.relatorio.profissionais = len(mapa)
        return mapa

    def _tipos(self, clinica):
        existentes = {_chave(t.nome): t for t in TipoAtendimento.objects.filter(clinica=clinica)}
        mapa = {}
        for linha in self.t.get("agenda_cor", []):
            nome = _texto(linha["nome"])[:60] or f"Tipo {linha['id']}"
            tipo = existentes.get(_chave(nome))
            if tipo is None:
                cor = _texto(linha["cor"])
                cor = cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else "#0d6efd"
                tipo = TipoAtendimento.objects.create(clinica=clinica, nome=nome, cor=cor.lower())
                existentes[_chave(nome)] = tipo
                self.relatorio.tipos_criados += 1
            mapa[linha["id"]] = tipo
        return mapa

    def _paciente(self, linha, clinica, cidades, estados_civis, logradouros, bairros, usados):
        avisos = self.relatorio.avisos
        extras = [f"Código no sistema antigo: {linha['id']}"]
        tipo = Paciente.Tipo.JURIDICA if linha["tipo_pessoa"] == "J" else Paciente.Tipo.FISICA
        nome = _texto(linha["nome"]) or f"Sem nome (código {linha['id']})"

        documento, original = _documento(linha["cpf_cnpj"], tipo)
        if documento and documento in usados:
            documento, original = "", _texto(linha["cpf_cnpj"])
            avisos["CPF/CNPJ repetido (guardado nas observações)"] += 1
        elif original:
            avisos["CPF/CNPJ inválido (guardado nas observações)"] += 1
        if original:
            extras.append(f"CPF/CNPJ no sistema antigo: {original}")
        if documento:
            usados.add(documento)

        telefones = {}
        for campo, legado in (
            ("telefone_residencial", "fone_res"),
            ("telefone_comercial", "fone_com"),
            ("telefone_celular", "fone_cel"),
        ):
            numero = somente_digitos(linha[legado])
            if len(numero) > 11:
                extras.append(f"Telefone ({legado}): {linha[legado]}")
                numero = ""
            elif numero and len(numero) < 10:
                avisos["Telefones sem DDD (mantidos como estavam)"] += 1
            telefones[campo] = numero
        if _texto(linha["fone_fax"]):
            extras.append(f"Fax: {_texto(linha['fone_fax'])}")

        email, email_invalido = _email(linha["email"])
        if email_invalido:
            extras.append(f"E-mail no sistema antigo: {email_invalido}")
            avisos["E-mail inválido (guardado nas observações)"] += 1

        cep = somente_digitos(linha["cep"])
        if cep and len(cep) != 8:
            extras.append(f"CEP no sistema antigo: {linha['cep']}")
            avisos["CEP incompleto (guardado nas observações)"] += 1
            cep = ""

        uf = cidade = None
        if linha["id_cidade"]:
            uf, cidade, nome_cidade, sigla = cidades.get(linha["id_cidade"], (None, None, "", None))
            if cidade is None:
                extras.append(f"Cidade no sistema antigo: {nome_cidade}/{sigla or '?'}")
                avisos["Cidade não encontrada na lista do IBGE (guardada nas observações)"] += 1

        sexo = linha["sexo"] if linha["sexo"] in ("F", "M") else ""
        nascimento = _data(linha["data_nasc"])
        if nascimento is not None and nascimento > self.hoje:
            extras.append(f"Data de nascimento no sistema antigo: {linha['data_nasc']}")
            nascimento = None

        saldo = float(linha["saldo"] or 0)
        if saldo:
            extras.append(f"Saldo: R$ {saldo:.2f}".replace(".", ","))
        pagamento = _data(linha["data_pgto"])
        if pagamento:
            extras.append(f"Último pagamento: {pagamento:%d/%m/%Y}")
        if _texto(linha["agencia"]) or _texto(linha["conta"]):
            extras.append(
                f"Banco {linha['id_banco']}, agência {_texto(linha['agencia'])}, "
                f"conta {_texto(linha['conta'])}"
            )
        for legado, rotulo in (("homepage", "Site"), ("msn", "MSN"), ("rg_obs", "Obs. do RG")):
            if _texto(linha[legado]):
                extras.append(f"{rotulo}: {_texto(linha[legado])}")

        pf = tipo == Paciente.Tipo.FISICA
        paciente = Paciente(
            clinica=clinica,
            tipo=tipo,
            nome=_cabe(nome, 200, "Nome completo", extras),
            razao_social=""
            if pf
            else _cabe(_texto(linha["razao_social"]), 200, "Razão social", extras),
            cpf_cnpj=documento,
            rg=_cabe(_texto(linha["rg"]), 20, "RG", extras) if pf else "",
            inscricao_estadual="" if pf else _cabe(_texto(linha["insc_est"]), 20, "IE", extras),
            sexo=sexo if pf else "",
            data_nascimento=nascimento if pf else None,
            estado_civil=estados_civis.get(linha["estado_civil"]) if pf else None,
            profissao=_cabe(_texto(linha["profissao"]), 100, "Profissão", extras) if pf else "",
            responsavel=_cabe(_texto(linha["responsavel"]), 200, "Responsável", extras)
            if pf
            else "",
            email=email,
            cep=cep,
            uf=uf,
            cidade=cidade,
            bairro=_cabe(bairros.get(linha["id_bairrocomunidade"], ""), 100, "Bairro", extras),
            logradouro=_cabe(logradouros.get(linha["id_logradouro"], ""), 200, "Endereço", extras),
            numero=_cabe(_texto(linha["endereco_num"]), 10, "Número", extras),
            complemento=_cabe(_texto(linha["endereco_compl"]), 100, "Complemento", extras),
            ativo=linha["ativo"] != "N",
            **telefones,
        )
        observacoes = _texto(linha["obs"])
        bloco = "[Sistema antigo]\n" + "\n".join(extras)
        paciente.observacoes = f"{observacoes}\n\n{bloco}" if observacoes else bloco
        return paciente, _data(linha["data_cadast"])

    def _pacientes(self, clinica):
        cidades = self._cidades()
        estados_civis = self._estados_civis()
        logradouros = self._logradouros()
        bairros = {b["id"]: _texto(b["nome"]) for b in self.t.get("bairrocomunidade", [])}
        usados = set()
        pares = [
            (
                linha["id"],
                *self._paciente(
                    linha, clinica, cidades, estados_civis, logradouros, bairros, usados
                ),
            )
            for linha in sorted(self.t.get("pessoas", []), key=lambda linha: linha["id"])
        ]
        Paciente.objects.bulk_create([paciente for _, paciente, _ in pares], batch_size=500)
        # Keep the original registration date (auto_now_add only fills it on creation).
        com_data = []
        for _, paciente, cadastro in pares:
            if cadastro is not None:
                paciente.criado_em = timezone.make_aware(
                    datetime.datetime.combine(cadastro, datetime.time(12))
                )
                com_data.append(paciente)
        Paciente.objects.bulk_update(com_data, ["criado_em"], batch_size=500)
        self.relatorio.pacientes = len(pares)
        return {codigo: paciente for codigo, paciente, _ in pares}

    def _agendamentos(self, profissionais, tipos):
        avisos = self.relatorio.avisos
        novos = []
        for linha in sorted(self.t.get("agendax", []), key=lambda linha: linha["id"]):
            profissional = profissionais.get(linha["id_dentista"])
            tipo = tipos.get(linha["id_cor"])
            dia = _data(linha["data_marcar"])
            inicio, fim = _hora(linha["hora_inicial"]), _hora(linha["hora_final"])
            if None in (profissional, tipo, dia, inicio, fim):
                avisos["Agendamento sem profissional, tipo ou data válidos (não importado)"] += 1
                continue
            # Blocked slots ("Ocupado") had no description; the schedule form requires a
            # patient or a description, so the type name keeps them editable.
            descricao = _texto(linha["descricao"]) or tipo.nome
            inicio = timezone.make_aware(datetime.datetime.combine(dia, inicio))
            fim = timezone.make_aware(datetime.datetime.combine(dia, fim))
            if fim <= inicio:
                fim = inicio + DURACAO_MINIMA
                descricao = f"{descricao}\n[Sistema antigo: horário de término corrigido]".strip()
                avisos["Agendamento com término antes do início (corrigido para 30 min)"] += 1
            novos.append(
                Agendamento(
                    clinica=profissional.clinica,
                    profissional=profissional,
                    tipo=tipo,
                    inicio=inicio,
                    fim=fim,
                    descricao=descricao,
                )
            )
        # The database forbids overlaps for the same practitioner: drop (and count) them.
        aceitos, ultimo_fim = [], {}
        for agendamento in sorted(novos, key=lambda a: (a.profissional.pk, a.inicio)):
            if agendamento.inicio < ultimo_fim.get(agendamento.profissional.pk, agendamento.inicio):
                avisos["Agendamento sobreposto a outro do mesmo profissional (não importado)"] += 1
                continue
            ultimo_fim[agendamento.profissional.pk] = agendamento.fim
            aceitos.append(agendamento)
        Agendamento.objects.bulk_create(aceitos, batch_size=1000)
        self.relatorio.agendamentos = len(aceitos)
        if aceitos:
            self._ampliar_horario(aceitos[0].clinica, aceitos)

    def _ampliar_horario(self, clinica, agendamentos):
        """Widen the clinic's schedule hours so every imported appointment shows in the grid."""
        passo = clinica.agenda_intervalo

        def minutos(momento):
            local = timezone.localtime(momento)
            return local.hour * 60 + local.minute

        primeiro = min(minutos(a.inicio) for a in agendamentos) // passo * passo
        ultimo = -(-max(minutos(a.fim) or 24 * 60 for a in agendamentos) // passo) * passo
        inicio = min(clinica.agenda_inicio, datetime.time(primeiro // 60, primeiro % 60))
        fim = clinica.agenda_fim
        if ultimo < 24 * 60:
            fim = max(fim, datetime.time(ultimo // 60, ultimo % 60))
        if (inicio, fim) != (clinica.agenda_inicio, clinica.agenda_fim):
            clinica.agenda_inicio, clinica.agenda_fim = inicio, fim
            clinica.save(update_fields=["agenda_inicio", "agenda_fim"])
            self.relatorio.avisos[
                f"Horário da agenda ampliado para {inicio:%H:%M}–{fim:%H:%M} "
                "(havia atendimentos fora do padrão)"
            ] += 1

    def _rechamadas(self, pacientes):
        avisos = self.relatorio.avisos
        novas = []
        for linha in self.t.get("agenda", []):
            if not linha.get("is_rechamada"):
                continue
            paciente = pacientes.get(linha["id_pessoa"])
            dia = _data(linha["data_marcar"])
            if paciente is None or dia is None:
                avisos["Rechamada de paciente inexistente ou sem data (não importada)"] += 1
                continue
            descricao = _texto(linha["descricao"]) or "Rechamada"
            if len(descricao) > 200:
                paciente.observacoes += f"\nRechamada de {dia:%d/%m/%Y}: {descricao}"
                paciente.save(update_fields=["observacoes"])
                descricao = descricao[:199] + "…"
            # The legacy system had no "done" flag: past recalls are considered handled.
            novas.append(
                Rechamada(
                    clinica=paciente.clinica,
                    paciente=paciente,
                    data=dia,
                    descricao=descricao,
                    concluida=dia < self.hoje,
                )
            )
        Rechamada.objects.bulk_create(novas)
        self.relatorio.rechamadas = len(novas)

    def executar(self):
        with transaction.atomic(), sem_isolamento():
            clinica = self._clinica()
            profissionais = self._profissionais(clinica)
            tipos = self._tipos(clinica)
            pacientes = self._pacientes(clinica)
            self._agendamentos(profissionais, tipos)
            self._rechamadas(pacientes)
            r = self.relatorio
            registrar(
                RegistroAuditoria.Acao.CRIAR,
                clinica=clinica,
                descricao=(
                    f"Importação do sistema antigo: {r.pacientes} pacientes, "
                    f"{r.agendamentos} agendamentos, {r.rechamadas} rechamadas"
                ),
            )
        return self.relatorio


def importar(texto_do_dump, nome_clinica, hoje=None):
    """Import a legacy dump into the clinic `nome_clinica` (created if needed). All or nothing."""
    tabelas = ler_tabelas(texto_do_dump, TABELAS)
    if not tabelas.get("pessoas"):
        raise ImportacaoRecusada("O arquivo não tem a tabela `pessoas` do sistema antigo.")
    return _Importador(tabelas, nome_clinica, hoje or timezone.localdate()).executar()
