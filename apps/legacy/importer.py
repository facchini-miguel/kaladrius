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

from apps.audit.models import AuditEntry
from apps.audit.record import log_event
from apps.core.isolation import without_isolation
from apps.core.models import Clinic
from apps.core.validators import (
    digits_only,
    ninth_digit,
    normalize_cnpj,
    valid_cnpj,
    valid_cpf,
)
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.reference_data.models import City, MaritalStatus, State
from apps.schedule.models import Appointment, AppointmentType

from .dump import read_tables

TABLES = {
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
MIN_DURATION = datetime.timedelta(minutes=30)


class ImportRefused(Exception):
    pass


@dataclass
class Report:
    clinic: Clinic | None = None
    practitioners: int = 0
    tipos_criados: int = 0
    patients: int = 0
    appointments: int = 0
    recalls: int = 0
    avisos: Counter = field(default_factory=Counter)


# UTF-8 bytes of Portuguese letters read as Latin-1: "Ã£" instead of "ã", "Âº" instead of "º".
_MOJIBAKE = re.compile("[\u00c2\u00c3][\u0080-\u00bf]")


def _text(value):
    """Clean text: fixes UTF-8 read as Latin-1 ("JoÃ£o") and normalizes line breaks."""
    text = "" if value is None else str(value)
    text = _MOJIBAKE.sub(lambda m: m.group().encode("latin-1").decode("utf-8"), text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _key(text):
    """Comparison key: no accents, lowercase, only letters and digits."""
    sem_acentos = unicodedata.normalize("NFKD", _text(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acentos.lower())


def _date(value):
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None  # MySQL "0000-00-00"


def _time(value):
    try:
        return datetime.time.fromisoformat(str(value))
    except ValueError:
        return None


def _email(value):
    email = _text(value)
    if not email:
        return "", None
    try:
        validate_email(email)
    except ValidationError:
        return "", email
    return email, None


def _document(bruto, kind):
    """(valid document, None) or ("", original text) when it cannot be used."""
    original = _text(bruto)
    document = normalize_cnpj(original)
    if not document:
        return "", None
    so_digitos = document.isascii() and document.isdigit()
    if kind == Patient.Kind.INDIVIDUAL:
        if so_digitos and 8 <= len(document) <= 11:
            document = document.zfill(11)  # leading zeros lost in the legacy system
        # cpf_valido ignores letters, so "123.456.789-09X" must be rejected here.
        return (document, None) if so_digitos and valid_cpf(document) else ("", original)
    if so_digitos and 12 <= len(document) <= 14:
        document = document.zfill(14)
    return (document, None) if valid_cnpj(document) else ("", original)


def _fits(value, size, label, extras):
    """The value if it fits the field; otherwise it goes in full to the notes."""
    if len(value) <= size:
        return value
    extras.append(f"{label}: {value}")
    return value[:size]


class _Importer:
    def __init__(self, tables, nome_clinica, today):
        self.t = tables
        self.nome_clinica = nome_clinica
        self.today = today
        self.relatorio = Report()

    # --- Lookups -----------------------------------------------------------------

    def _cities(self):
        """Legacy city id → (UF, IBGE city or None, legacy name)."""
        ufs_legado = {u["id"]: _text(u["sigla"]).upper() for u in self.t.get("uf", [])}
        ufs = {state.abbreviation: state for state in State.objects.all()}
        ibge = defaultdict(dict)
        for city in City.objects.select_related("state"):
            ibge[city.state.abbreviation][_key(city.name)] = city
        resultado = {}
        for row in self.t.get("cidade", []):
            id_uf = str(row["id_uf"] or "")
            abbreviation = ufs_legado.get(int(id_uf)) if id_uf.isdecimal() else None
            name = _text(row["cidade"])
            resultado[row["id"]] = (
                ufs.get(abbreviation),
                ibge[abbreviation].get(_key(name)),
                name,
                abbreviation,
            )
        return resultado

    def _marital_statuses(self):
        novos = {_key(e.name)[:5]: e for e in MaritalStatus.objects.all()}
        return {
            row["id"]: novos.get(_key(row["nome"])[:5])
            for row in self.t.get("pessoas_estado_civil", [])
        }

    def _streets(self):
        tipos = {t["id"]: _text(t["nome"]).title() for t in self.t.get("tipo_endereco", [])}
        resultado = {}
        for row in self.t.get("logradouro", []):
            kind = tipos.get(row["id_tipo_endereco"], "")
            name = _text(row["nome"])
            resultado[row["id"]] = f"{kind} {name}" if kind and kind != "Outros" else name
        return resultado

    # --- Steps -------------------------------------------------------------------

    def _clinic(self):
        clinic = Clinic.objects.filter(name=self.nome_clinica).first()
        if clinic is not None and Patient.objects.filter(clinic=clinic).exists():
            raise ImportRefused(
                f"A clínica “{self.nome_clinica}” já tem pacientes. A importação só é feita "
                "numa clínica nova ou vazia, para não duplicar dados."
            )
        if clinic is None:
            clinic = Clinic.objects.create(name=self.nome_clinica)  # gets the default types
        self.relatorio.clinic = clinic
        return clinic

    def _practitioners(self, clinic):
        mapa = {}
        for row in self.t.get("dentistas", []):
            name = _text(row["nome"]).lstrip("_ ").strip() or f"Profissional {row['id']}"
            mapa[row["id"]] = Practitioner.objects.create(clinic=clinic, name=name[:200])
        self.relatorio.practitioners = len(mapa)
        return mapa

    def _types(self, clinic):
        existentes = {_key(t.name): t for t in AppointmentType.objects.filter(clinic=clinic)}
        mapa = {}
        for row in self.t.get("agenda_cor", []):
            name = _text(row["nome"])[:60] or f"Tipo {row['id']}"
            kind = existentes.get(_key(name))
            if kind is None:
                color = _text(row["cor"])
                color = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#0d6efd"
                kind = AppointmentType.objects.create(clinic=clinic, name=name, color=color.lower())
                existentes[_key(name)] = kind
                self.relatorio.tipos_criados += 1
            mapa[row["id"]] = kind
        return mapa

    def _patient(self, row, clinic, cidades, estados_civis, logradouros, bairros, usados):
        avisos = self.relatorio.avisos
        extras = [f"Código no sistema antigo: {row['id']}"]
        kind = Patient.Kind.COMPANY if row["tipo_pessoa"] == "J" else Patient.Kind.INDIVIDUAL
        name = _text(row["nome"]) or f"Sem nome (código {row['id']})"

        document, original = _document(row["cpf_cnpj"], kind)
        if document and document in usados:
            document, original = "", _text(row["cpf_cnpj"])
            avisos["CPF/CNPJ repetido (guardado nas observações)"] += 1
        elif original:
            avisos["CPF/CNPJ inválido (guardado nas observações)"] += 1
        if original:
            extras.append(f"CPF/CNPJ no sistema antigo: {original}")
        if document:
            usados.add(document)

        telefones = {}
        for phone_field, legado in (
            ("home_phone", "fone_res"),
            ("work_phone", "fone_com"),
            ("mobile_phone", "fone_cel"),
        ):
            number = digits_only(row[legado])
            if len(number) > 11:
                extras.append(f"Telefone ({legado}): {row[legado]}")
                number = ""
            elif number and len(number) < 10:
                avisos["Telefones sem DDD (mantidos como estavam)"] += 1
            if len(number) == 11 and number.startswith("0"):  # carrier prefix: 0 + DDD
                number = number[1:]
            # The legacy predates the ninth mobile digit (2012-2016): old mobiles get it.
            telefones[phone_field] = ninth_digit(number)
        if _text(row["fone_fax"]):
            extras.append(f"Fax: {_text(row['fone_fax'])}")

        email, email_invalido = _email(row["email"])
        if email_invalido:
            extras.append(f"E-mail no sistema antigo: {email_invalido}")
            avisos["E-mail inválido (guardado nas observações)"] += 1

        postal_code = digits_only(row["cep"])
        if postal_code and len(postal_code) != 8:
            extras.append(f"CEP no sistema antigo: {row['cep']}")
            avisos["CEP incompleto (guardado nas observações)"] += 1
            postal_code = ""

        state = city = None
        if row["id_cidade"]:
            state, city, nome_cidade, abbreviation = cidades.get(
                row["id_cidade"], (None, None, "", None)
            )
            if city is None:
                extras.append(f"Cidade no sistema antigo: {nome_cidade}/{abbreviation or '?'}")
                avisos["Cidade não encontrada na lista do IBGE (guardada nas observações)"] += 1

        sex = row["sexo"] if row["sexo"] in ("F", "M") else ""
        nascimento = _date(row["data_nasc"])
        if nascimento is not None and nascimento > self.today:
            extras.append(f"Data de nascimento no sistema antigo: {row['data_nasc']}")
            nascimento = None

        saldo = float(row["saldo"] or 0)
        if saldo:
            extras.append(f"Saldo: R$ {saldo:.2f}".replace(".", ","))
        payment = _date(row["data_pgto"])
        if payment:
            extras.append(f"Último pagamento: {payment:%d/%m/%Y}")
        if _text(row["agencia"]) or _text(row["conta"]):
            extras.append(
                f"Banco {row['id_banco']}, agência {_text(row['agencia'])}, "
                f"conta {_text(row['conta'])}"
            )
        for legado, label in (("homepage", "Site"), ("msn", "MSN"), ("rg_obs", "Obs. do RG")):
            if _text(row[legado]):
                extras.append(f"{label}: {_text(row[legado])}")

        pf = kind == Patient.Kind.INDIVIDUAL
        patient = Patient(
            clinic=clinic,
            kind=kind,
            name=_fits(name, 200, "Nome completo", extras),
            legal_name="" if pf else _fits(_text(row["razao_social"]), 200, "Razão social", extras),
            tax_id=document,
            rg=_fits(_text(row["rg"]), 20, "RG", extras) if pf else "",
            state_registration="" if pf else _fits(_text(row["insc_est"]), 20, "IE", extras),
            sex=sex if pf else "",
            birth_date=nascimento if pf else None,
            marital_status=estados_civis.get(row["estado_civil"]) if pf else None,
            occupation=_fits(_text(row["profissao"]), 100, "Profissão", extras) if pf else "",
            guardian=_fits(_text(row["responsavel"]), 200, "Responsável", extras) if pf else "",
            email=email,
            postal_code=postal_code,
            state=state,
            city=city,
            neighborhood=_fits(bairros.get(row["id_bairrocomunidade"], ""), 100, "Bairro", extras),
            street=_fits(logradouros.get(row["id_logradouro"], ""), 200, "Endereço", extras),
            number=_fits(_text(row["endereco_num"]), 10, "Número", extras),
            complement=_fits(_text(row["endereco_compl"]), 100, "Complemento", extras),
            active=row["ativo"] != "N",
            **telefones,
        )
        notes = _text(row["obs"])
        bloco = "[Sistema antigo]\n" + "\n".join(extras)
        patient.notes = f"{notes}\n\n{bloco}" if notes else bloco
        return patient, _date(row["data_cadast"])

    def _patients(self, clinic):
        cidades = self._cities()
        estados_civis = self._marital_statuses()
        logradouros = self._streets()
        bairros = {b["id"]: _text(b["nome"]) for b in self.t.get("bairrocomunidade", [])}
        usados = set()
        pares = [
            (
                row["id"],
                *self._patient(row, clinic, cidades, estados_civis, logradouros, bairros, usados),
            )
            for row in sorted(self.t.get("pessoas", []), key=lambda row: row["id"])
        ]
        Patient.objects.bulk_create([patient for _, patient, _ in pares], batch_size=500)
        # Keep the original registration date (auto_now_add only fills it on creation).
        com_data = []
        for _, patient, cadastro in pares:
            if cadastro is not None:
                patient.created_at = timezone.make_aware(
                    datetime.datetime.combine(cadastro, datetime.time(12))
                )
                com_data.append(patient)
        Patient.objects.bulk_update(com_data, ["created_at"], batch_size=500)
        self.relatorio.patients = len(pares)
        return {code: patient for code, patient, _ in pares}

    def _appointments(self, practitioners, tipos):
        avisos = self.relatorio.avisos
        novos = []
        for row in sorted(self.t.get("agendax", []), key=lambda row: row["id"]):
            practitioner = practitioners.get(row["id_dentista"])
            kind = tipos.get(row["id_cor"])
            day = _date(row["data_marcar"])
            start, end = _time(row["hora_inicial"]), _time(row["hora_final"])
            if None in (practitioner, kind, day, start, end):
                avisos["Agendamento sem profissional, tipo ou data válidos (não importado)"] += 1
                continue
            # Blocked slots ("Ocupado") had no description; the schedule form requires a
            # patient or a description, so the type name keeps them editable.
            description = _text(row["descricao"]) or kind.name
            start = timezone.make_aware(datetime.datetime.combine(day, start))
            end = timezone.make_aware(datetime.datetime.combine(day, end))
            if end <= start:
                end = start + MIN_DURATION
                description = (
                    f"{description}\n[Sistema antigo: horário de término corrigido]".strip()
                )
                avisos["Agendamento com término antes do início (corrigido para 30 min)"] += 1
            novos.append(
                Appointment(
                    clinic=practitioner.clinic,
                    practitioner=practitioner,
                    kind=kind,
                    start=start,
                    end=end,
                    description=description,
                )
            )
        # The database forbids overlaps for the same practitioner: drop (and count) them.
        aceitos, ultimo_fim = [], {}
        for appointment in sorted(novos, key=lambda a: (a.practitioner.pk, a.start)):
            if appointment.start < ultimo_fim.get(appointment.practitioner.pk, appointment.start):
                avisos["Agendamento sobreposto a outro do mesmo profissional (não importado)"] += 1
                continue
            ultimo_fim[appointment.practitioner.pk] = appointment.end
            aceitos.append(appointment)
        Appointment.objects.bulk_create(aceitos, batch_size=1000)
        self.relatorio.appointments = len(aceitos)
        if aceitos:
            self._widen_hours(aceitos[0].clinic, aceitos)

    def _widen_hours(self, clinic, appointments):
        """Widen the clinic's schedule hours so every imported appointment shows in the grid."""
        passo = clinic.schedule_interval

        def minutos(timestamp):
            local = timezone.localtime(timestamp)
            return local.hour * 60 + local.minute

        first = min(minutos(a.start) for a in appointments) // passo * passo
        last = -(-max(minutos(a.end) or 24 * 60 for a in appointments) // passo) * passo
        start = min(clinic.schedule_start, datetime.time(first // 60, first % 60))
        end = clinic.schedule_end
        if last < 24 * 60:
            end = max(end, datetime.time(last // 60, last % 60))
        if (start, end) != (clinic.schedule_start, clinic.schedule_end):
            clinic.schedule_start, clinic.schedule_end = start, end
            clinic.save(update_fields=["schedule_start", "schedule_end"])
            self.relatorio.avisos[
                f"Horário da agenda ampliado para {start:%H:%M}–{end:%H:%M} "
                "(havia atendimentos fora do padrão)"
            ] += 1

    def _recalls(self, patients):
        avisos = self.relatorio.avisos
        novas = []
        for row in self.t.get("agenda", []):
            if not row.get("is_rechamada"):
                continue
            patient = patients.get(row["id_pessoa"])
            day = _date(row["data_marcar"])
            if patient is None or day is None:
                avisos["Rechamada de paciente inexistente ou sem data (não importada)"] += 1
                continue
            description = _text(row["descricao"]) or "Rechamada"
            if len(description) > 200:
                patient.notes += f"\nRechamada de {day:%d/%m/%Y}: {description}"
                patient.save(update_fields=["notes"])
                description = description[:199] + "…"
            # The legacy system had no "done" flag: past recalls are considered handled.
            novas.append(
                Recall(
                    clinic=patient.clinic,
                    patient=patient,
                    date=day,
                    description=description,
                    done=day < self.today,
                )
            )
        Recall.objects.bulk_create(novas)
        self.relatorio.recalls = len(novas)

    def run(self):
        with transaction.atomic(), without_isolation():
            clinic = self._clinic()
            practitioners = self._practitioners(clinic)
            tipos = self._types(clinic)
            patients = self._patients(clinic)
            self._appointments(practitioners, tipos)
            self._recalls(patients)
            r = self.relatorio
            log_event(
                AuditEntry.Action.CREATE,
                clinic=clinic,
                description=(
                    f"Importação do sistema antigo: {r.patients} pacientes, "
                    f"{r.appointments} agendamentos, {r.recalls} rechamadas"
                ),
            )
        return self.relatorio


def import_dump(texto_do_dump, nome_clinica, today=None):
    """Import a legacy dump into the clinic `nome_clinica` (created if needed). All or nothing."""
    tables = read_tables(texto_do_dump, TABLES)
    if not tables.get("pessoas"):
        raise ImportRefused("O arquivo não tem a tabela `pessoas` do sistema antigo.")
    return _Importer(tables, nome_clinica, today or timezone.localdate()).run()
