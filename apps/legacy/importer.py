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
    kinds_created: int = 0
    patients: int = 0
    appointments: int = 0
    recalls: int = 0
    warnings: Counter = field(default_factory=Counter)


# UTF-8 bytes of Portuguese letters read as Latin-1: "Ã£" instead of "ã", "Âº" instead of "º".
_MOJIBAKE = re.compile("[\u00c2\u00c3][\u0080-\u00bf]")


def _text(value):
    """Clean text: fixes UTF-8 read as Latin-1 ("JoÃ£o") and normalizes line breaks."""
    text = "" if value is None else str(value)
    text = _MOJIBAKE.sub(lambda m: m.group().encode("latin-1").decode("utf-8"), text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _key(text):
    """Comparison key: no accents, lowercase, only letters and digits."""
    unaccented = unicodedata.normalize("NFKD", _text(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", unaccented.lower())


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


def _document(raw, kind):
    """(valid document, None) or ("", original text) when it cannot be used."""
    original = _text(raw)
    document = normalize_cnpj(original)
    if not document:
        return "", None
    all_digits = document.isascii() and document.isdigit()
    if kind == Patient.Kind.INDIVIDUAL:
        if all_digits and 8 <= len(document) <= 11:
            document = document.zfill(11)  # leading zeros lost in the legacy system
        # cpf_valido ignores letters, so "123.456.789-09X" must be rejected here.
        return (document, None) if all_digits and valid_cpf(document) else ("", original)
    if all_digits and 12 <= len(document) <= 14:
        document = document.zfill(14)
    return (document, None) if valid_cnpj(document) else ("", original)


def _fits(value, size, label, extras):
    """The value if it fits the field; otherwise it goes in full to the notes."""
    if len(value) <= size:
        return value
    extras.append(f"{label}: {value}")
    return value[:size]


class _Importer:
    def __init__(self, tables, clinic_name, today):
        self.t = tables
        self.clinic_name = clinic_name
        self.today = today
        self.report = Report()

    # --- Lookups -----------------------------------------------------------------

    def _cities(self):
        """Legacy city id → (UF, IBGE city or None, legacy name)."""
        legacy_states = {u["id"]: _text(u["sigla"]).upper() for u in self.t.get("uf", [])}
        ufs = {state.abbreviation: state for state in State.objects.all()}
        ibge = defaultdict(dict)
        for city in City.objects.select_related("state"):
            ibge[city.state.abbreviation][_key(city.name)] = city
        result = {}
        for row in self.t.get("cidade", []):
            id_uf = str(row["id_uf"] or "")
            abbreviation = legacy_states.get(int(id_uf)) if id_uf.isdecimal() else None
            name = _text(row["cidade"])
            result[row["id"]] = (
                ufs.get(abbreviation),
                ibge[abbreviation].get(_key(name)),
                name,
                abbreviation,
            )
        return result

    def _marital_statuses(self):
        new_ones = {_key(e.name)[:5]: e for e in MaritalStatus.objects.all()}
        return {
            row["id"]: new_ones.get(_key(row["nome"])[:5])
            for row in self.t.get("pessoas_estado_civil", [])
        }

    def _streets(self):
        kinds = {t["id"]: _text(t["nome"]).title() for t in self.t.get("tipo_endereco", [])}
        result = {}
        for row in self.t.get("logradouro", []):
            kind = kinds.get(row["id_tipo_endereco"], "")
            name = _text(row["nome"])
            result[row["id"]] = f"{kind} {name}" if kind and kind != "Outros" else name
        return result

    # --- Steps -------------------------------------------------------------------

    def _clinic(self):
        clinic = Clinic.objects.filter(name=self.clinic_name).first()
        if clinic is not None and Patient.objects.filter(clinic=clinic).exists():
            raise ImportRefused(
                f"The clinic “{self.clinic_name}” already has patients. The import only goes "
                "into a new or empty clinic, so no data is duplicated."
            )
        if clinic is None:
            clinic = Clinic.objects.create(name=self.clinic_name)  # gets the default types
        self.report.clinic = clinic
        return clinic

    def _practitioners(self, clinic):
        mapping = {}
        for row in self.t.get("dentistas", []):
            name = _text(row["nome"]).lstrip("_ ").strip() or f"Profissional {row['id']}"
            mapping[row["id"]] = Practitioner.objects.create(clinic=clinic, name=name[:200])
        self.report.practitioners = len(mapping)
        return mapping

    def _types(self, clinic):
        existing = {_key(t.name): t for t in AppointmentType.objects.filter(clinic=clinic)}
        mapping = {}
        for row in self.t.get("agenda_cor", []):
            name = _text(row["nome"])[:60] or f"Tipo {row['id']}"
            kind = existing.get(_key(name))
            if kind is None:
                color = _text(row["cor"])
                color = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#0d6efd"
                kind = AppointmentType.objects.create(clinic=clinic, name=name, color=color.lower())
                existing[_key(name)] = kind
                self.report.kinds_created += 1
            mapping[row["id"]] = kind
        return mapping

    def _patient(self, row, clinic, cities, marital_statuses, streets, neighborhoods, used):
        warnings = self.report.warnings
        extras = [f"Código no sistema antigo: {row['id']}"]
        kind = Patient.Kind.COMPANY if row["tipo_pessoa"] == "J" else Patient.Kind.INDIVIDUAL
        name = _text(row["nome"]) or f"Sem nome (código {row['id']})"

        document, original = _document(row["cpf_cnpj"], kind)
        if document and document in used:
            document, original = "", _text(row["cpf_cnpj"])
            warnings["Repeated CPF/CNPJ (kept in the notes)"] += 1
        elif original:
            warnings["Invalid CPF/CNPJ (kept in the notes)"] += 1
        if original:
            extras.append(f"CPF/CNPJ no sistema antigo: {original}")
        if document:
            used.add(document)

        phones = {}
        for phone_field, legacy in (
            ("home_phone", "fone_res"),
            ("work_phone", "fone_com"),
            ("mobile_phone", "fone_cel"),
        ):
            number = digits_only(row[legacy])
            if len(number) > 11:
                extras.append(f"Telefone ({legacy}): {row[legacy]}")
                number = ""
            elif number and len(number) < 10:
                warnings["Phones without area code (kept as they were)"] += 1
            if len(number) == 11 and number.startswith("0"):  # carrier prefix: 0 + DDD
                number = number[1:]
            # The legacy predates the ninth mobile digit (2012-2016): old mobiles get it.
            phones[phone_field] = ninth_digit(number)
        if _text(row["fone_fax"]):
            extras.append(f"Fax: {_text(row['fone_fax'])}")

        email, invalid_email = _email(row["email"])
        if invalid_email:
            extras.append(f"E-mail no sistema antigo: {invalid_email}")
            warnings["Invalid e-mail (kept in the notes)"] += 1

        postal_code = digits_only(row["cep"])
        if postal_code and len(postal_code) != 8:
            extras.append(f"CEP no sistema antigo: {row['cep']}")
            warnings["Incomplete CEP (kept in the notes)"] += 1
            postal_code = ""

        state = city = None
        if row["id_cidade"]:
            state, city, city_name, abbreviation = cities.get(
                row["id_cidade"], (None, None, "", None)
            )
            if city is None:
                extras.append(f"Cidade no sistema antigo: {city_name}/{abbreviation or '?'}")
                warnings["City not in the IBGE list (kept in the notes)"] += 1

        sex = row["sexo"] if row["sexo"] in ("F", "M") else ""
        birth_date = _date(row["data_nasc"])
        if birth_date is not None and birth_date > self.today:
            extras.append(f"Data de nascimento no sistema antigo: {row['data_nasc']}")
            birth_date = None

        balance = float(row["saldo"] or 0)
        if balance:
            extras.append(f"Saldo: R$ {balance:.2f}".replace(".", ","))
        payment = _date(row["data_pgto"])
        if payment:
            extras.append(f"Último pagamento: {payment:%d/%m/%Y}")
        if _text(row["agencia"]) or _text(row["conta"]):
            extras.append(
                f"Banco {row['id_banco']}, agência {_text(row['agencia'])}, "
                f"conta {_text(row['conta'])}"
            )
        for legacy, label in (("homepage", "Site"), ("msn", "MSN"), ("rg_obs", "Obs. do RG")):
            if _text(row[legacy]):
                extras.append(f"{label}: {_text(row[legacy])}")

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
            birth_date=birth_date if pf else None,
            marital_status=marital_statuses.get(row["estado_civil"]) if pf else None,
            occupation=_fits(_text(row["profissao"]), 100, "Profissão", extras) if pf else "",
            guardian=_fits(_text(row["responsavel"]), 200, "Responsável", extras) if pf else "",
            email=email,
            postal_code=postal_code,
            state=state,
            city=city,
            neighborhood=_fits(
                neighborhoods.get(row["id_bairrocomunidade"], ""), 100, "Bairro", extras
            ),
            street=_fits(streets.get(row["id_logradouro"], ""), 200, "Endereço", extras),
            number=_fits(_text(row["endereco_num"]), 10, "Número", extras),
            complement=_fits(_text(row["endereco_compl"]), 100, "Complemento", extras),
            active=row["ativo"] != "N",
            **phones,
        )
        notes = _text(row["obs"])
        block = "[Sistema antigo]\n" + "\n".join(extras)
        patient.notes = f"{notes}\n\n{block}" if notes else block
        return patient, _date(row["data_cadast"])

    def _patients(self, clinic):
        cities = self._cities()
        marital_statuses = self._marital_statuses()
        streets = self._streets()
        neighborhoods = {b["id"]: _text(b["nome"]) for b in self.t.get("bairrocomunidade", [])}
        used = set()
        pares = [
            (
                row["id"],
                *self._patient(row, clinic, cities, marital_statuses, streets, neighborhoods, used),
            )
            for row in sorted(self.t.get("pessoas", []), key=lambda row: row["id"])
        ]
        Patient.objects.bulk_create([patient for _, patient, _ in pares], batch_size=500)
        # Keep the original registration date (auto_now_add only fills it on creation).
        com_data = []
        for _, patient, record in pares:
            if record is not None:
                patient.created_at = timezone.make_aware(
                    datetime.datetime.combine(record, datetime.time(12))
                )
                com_data.append(patient)
        Patient.objects.bulk_update(com_data, ["created_at"], batch_size=500)
        self.report.patients = len(pares)
        return {code: patient for code, patient, _ in pares}

    def _appointments(self, practitioners, kinds):
        warnings = self.report.warnings
        new_ones = []
        for row in sorted(self.t.get("agendax", []), key=lambda row: row["id"]):
            practitioner = practitioners.get(row["id_dentista"])
            kind = kinds.get(row["id_cor"])
            day = _date(row["data_marcar"])
            start, end = _time(row["hora_inicial"]), _time(row["hora_final"])
            if None in (practitioner, kind, day, start, end):
                warnings[
                    "Appointment without a valid practitioner, type or date (not imported)"
                ] += 1
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
                warnings["Appointment ending before it starts (set to 30 min)"] += 1
            new_ones.append(
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
        accepted, last_end = [], {}
        for appointment in sorted(new_ones, key=lambda a: (a.practitioner.pk, a.start)):
            if appointment.start < last_end.get(appointment.practitioner.pk, appointment.start):
                warnings[
                    "Agendamento sobreposto a outro do mesmo profissional (não importado)"
                ] += 1
                continue
            last_end[appointment.practitioner.pk] = appointment.end
            accepted.append(appointment)
        Appointment.objects.bulk_create(accepted, batch_size=1000)
        self.report.appointments = len(accepted)
        if accepted:
            self._widen_hours(accepted[0].clinic, accepted)

    def _widen_hours(self, clinic, appointments):
        """Widen the clinic's schedule hours so every imported appointment shows in the grid."""
        step = clinic.schedule_interval

        def minutes(timestamp):
            local = timezone.localtime(timestamp)
            return local.hour * 60 + local.minute

        first = min(minutes(a.start) for a in appointments) // step * step
        last = -(-max(minutes(a.end) or 24 * 60 for a in appointments) // step) * step
        start = min(clinic.schedule_start, datetime.time(first // 60, first % 60))
        end = clinic.schedule_end
        if last < 24 * 60:
            end = max(end, datetime.time(last // 60, last % 60))
        if (start, end) != (clinic.schedule_start, clinic.schedule_end):
            clinic.schedule_start, clinic.schedule_end = start, end
            clinic.save(update_fields=["schedule_start", "schedule_end"])
            self.report.warnings[
                f"Horário da agenda ampliado para {start:%H:%M}–{end:%H:%M} "
                "(havia atendimentos fora do padrão)"
            ] += 1

    def _recalls(self, patients):
        warnings = self.report.warnings
        novas = []
        for row in self.t.get("agenda", []):
            if not row.get("is_rechamada"):
                continue
            patient = patients.get(row["id_pessoa"])
            day = _date(row["data_marcar"])
            if patient is None or day is None:
                warnings["Recall of a missing patient or without a date (not imported)"] += 1
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
        self.report.recalls = len(novas)

    def run(self):
        with transaction.atomic(), without_isolation():
            clinic = self._clinic()
            practitioners = self._practitioners(clinic)
            kinds = self._types(clinic)
            patients = self._patients(clinic)
            self._appointments(practitioners, kinds)
            self._recalls(patients)
            r = self.report
            log_event(
                AuditEntry.Action.CREATE,
                clinic=clinic,
                description=(
                    f"Importação do sistema antigo: {r.patients} pacientes, "
                    f"{r.appointments} agendamentos, {r.recalls} rechamadas"
                ),
            )
        return self.report


def import_dump(dump_text, clinic_name, today=None):
    """Import a legacy dump into the clinic `nome_clinica` (created if needed). All or nothing."""
    tables = read_tables(dump_text, TABLES)
    if not tables.get("pessoas"):
        raise ImportRefused("The file does not have the old system's `pessoas` table.")
    return _Importer(tables, clinic_name, today or timezone.localdate()).run()
