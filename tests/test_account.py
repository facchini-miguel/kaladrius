"""Login protections asked by the owner (decision 111): leaving after 30 idle minutes, a limit
of wrong logins per address, two-step verification with an authenticator app (QR code),
password recovery by e-mail and the eye button on password fields."""

import time

import pyotp
import pytest
from axes.models import AccessAttempt
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.account import services
from apps.account.models import RecoveryCode, TwoFactor
from apps.audit.models import AuditEntry
from apps.core.models import Role

pytestmark = pytest.mark.django_db
PASSWORD = "Senha-Ficticia-2026!"


@pytest.fixture
def person(clinic_a, create_user):
    user = create_user("pessoa_conta", clinic_a, Role.FRONT_DESK)
    user.set_password(PASSWORD)
    user.email = "pessoa@example.com"
    user.save()
    return user


def log_in(client, user, password=PASSWORD, next_one=""):
    data = {"username": user.username, "password": password}
    if next_one:
        data["next"] = next_one
    return client.post(reverse("login"), data)


def enable_two_factor(user):
    device = services.prepare(user)
    codes = services.activate(device)
    return device, codes


def current_code(device, offset=0):
    totp = pyotp.TOTP(device.secret)
    return totp.at(time.time() + offset * totp.interval)


# --- Idle time and the eye button ----------------------------------------------------------


def test_session_ends_after_30_idle_minutes(client, person):
    assert settings.SESSION_COOKIE_AGE == 30 * 60 and settings.SESSION_SAVE_EVERY_REQUEST
    client.force_login(person)
    page = client.get(reverse("home")).content.decode()
    assert 'data-idle-minutes="30"' in page and reverse("account:active") in page
    assert client.get(reverse("account:active")).status_code == 204
    logged_out = client.get(reverse("login"), {"idle": "1"})
    assert "30 minutos sem uso" in logged_out.content.decode()


def test_active_without_login_goes_to_login(client):
    assert client.get(reverse("account:active")).status_code == 302


def test_password_fields_get_the_eye_toggle(client):
    page = client.get(reverse("login")).content.decode()
    assert 'data-show-password="Mostrar a senha"' in page


# --- Wrong logins per address ---------------------------------------------------------------


def test_many_attempts_from_one_address_block_any_user(client, person):
    for number in range(4):  # 4 usernames x 5 failures: 20 from 127.0.0.1
        AccessAttempt.objects.create(
            username=f"tentativa{number}",
            ip_address="127.0.0.1",
            user_agent="teste",
            failures_since_start=5,
            get_data="",
            post_data="",
            http_accept="",
            path_info="/",
            attempt_time=timezone.now(),
        )
    response = log_in(client, person)
    assert response.status_code == 200
    assert "Muitas tentativas erradas a partir deste endereço" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_few_attempts_from_the_address_do_not_block(client, person):
    AccessAttempt.objects.create(
        username="outro",
        ip_address="127.0.0.1",
        user_agent="teste",
        failures_since_start=3,
        get_data="",
        post_data="",
        http_accept="",
        path_info="/",
        attempt_time=timezone.now(),
    )
    assert log_in(client, person).status_code == 302


# --- Two-step verification --------------------------------------------------------------------


def test_activate_with_qr_code(client, person):
    client.force_login(person)
    page = client.get(reverse("account:two_factor")).content.decode()
    assert "<svg" in page and "otpauth" not in page  # the secret is in the QR, not text
    device = TwoFactor.objects.get(user=person)
    wrong = client.post(reverse("account:two_factor"), {"action": "ativar", "code": "000000"})
    assert "Código incorreto" in wrong.content.decode()
    response = client.post(
        reverse("account:two_factor"), {"action": "ativar", "code": current_code(device)}
    )
    text = response.content.decode()
    assert "Verificação em duas etapas ativada" in text
    assert RecoveryCode.objects.filter(user=person).count() == 10
    assert AuditEntry.objects.filter(object_repr__contains="ativada").exists()
    device.refresh_from_db()
    assert device.active and device.secret not in text


def test_login_asks_for_the_code_after_the_password(client, person):
    device, _ = enable_two_factor(person)
    response = log_in(client, person, next_one=reverse("patients:list"))
    assert response.url == reverse("account:code")
    assert "_auth_user_id" not in client.session  # not logged in yet
    wrong = client.post(reverse("account:code"), {"code": "123456"})
    assert "Código incorreto" in wrong.content.decode()
    assert AccessAttempt.objects.filter(username=person.username).exists()  # counted
    code = current_code(device)
    right = client.post(reverse("account:code"), {"code": code})
    assert right.url == reverse("patients:list")
    assert client.session["_auth_user_id"] == str(person.pk)
    # The same code does not work twice.
    client.logout()
    log_in(client, person)
    repeated_one = client.post(reverse("account:code"), {"code": code})
    assert "Código incorreto" in repeated_one.content.decode()


def test_recovery_code_works_once(client, person):
    _, codes = enable_two_factor(person)
    log_in(client, person)
    assert client.post(reverse("account:code"), {"code": codes[0].lower()}).status_code == 302
    client.logout()
    log_in(client, person)
    second = client.post(reverse("account:code"), {"code": codes[0]})
    assert "Código incorreto" in second.content.decode()


def test_five_wrong_codes_return_to_login(client, person):
    enable_two_factor(person)
    log_in(client, person)
    for _ in range(5):
        client.post(reverse("account:code"), {"code": "000000"})
    # Like 5 wrong passwords: the login protection locks the user for an hour.
    assert client.get(reverse("account:code")).url == reverse("login")
    blocked = log_in(client, person)
    assert "_auth_user_id" not in client.session and blocked.status_code != 302


def test_code_step_expires(client, person):
    device, _ = enable_two_factor(person)
    log_in(client, person)
    session = client.session
    session["duas_etapas_pendente"]["momento"] -= 10 * 60
    session.save()
    assert client.post(reverse("account:code"), {"code": current_code(device)}).url == (
        reverse("login")
    )


def test_deactivate_and_generate_new_codes(client, person):
    device, old_ones = enable_two_factor(person)
    client.force_login(person)
    new_items = client.post(
        reverse("account:two_factor"),
        {"action": "codigos", "codes-code": current_code(device)},
    )
    assert "Códigos de recuperação" in new_items.content.decode()
    assert not services.verify_recovery(person, old_ones[1])  # old ones stop working
    wrong = client.post(
        reverse("account:two_factor"),
        {"action": "desativar", "disable-password": "errada", "disable-code": "000000"},
    )
    assert "Senha incorreta" in wrong.content.decode()
    response = client.post(
        reverse("account:two_factor"),
        {
            "action": "desativar",
            "disable-password": PASSWORD,
            "disable-code": current_code(device, offset=1),
        },
    )
    assert response.status_code == 302 and not services.active_for(person)


def test_admin_removes_verification_of_who_lost_the_phone(client, clinic_a, person, create_user):
    enable_two_factor(person)
    admin = create_user("admin_conta", clinic_a, Role.ADMIN)
    client.force_login(admin)
    membership = person.memberships.get()
    page = client.get(reverse("team:edit", args=[membership.pk])).content.decode()
    assert "Remover a verificação em duas etapas" in page
    client.post(reverse("team:two_factor", args=[membership.pk]))
    assert not services.active_for(person)
    assert AuditEntry.objects.filter(object_repr__contains="removida").exists()


def test_demo_account_does_not_activate(client, person):
    person.demo = True
    person.save(update_fields=["demo"])
    client.force_login(person)
    assert client.get(reverse("account:two_factor")).status_code == 302
    assert not TwoFactor.objects.exists()


# --- Password recovery by e-mail -------------------------------------------------------------


def test_no_email_configured_means_no_recovery(client, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = False
    assert client.get(reverse("account:recover")).status_code == 404
    assert "Esqueci minha senha" not in client.get(reverse("login")).content.decode()


def test_recover_password_by_email(client, person, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    assert "Esqueci minha senha" in client.get(reverse("login")).content.decode()
    response = client.post(reverse("account:recover"), {"email": "pessoa@example.com"})
    assert response.url == reverse("account:recovery_sent")
    [message] = mail.outbox
    assert "pessoa_conta" in message.body and "Kaladrius" in message.subject
    link = next(row for row in message.body.splitlines() if "/account/password/new/" in row)
    path = link.split("testserver", 1)[1]
    form_page = client.get(path, follow=True)
    new_one = "Nova-Senha-Ficticia-77"
    client.post(
        form_page.redirect_chain[-1][0], {"new_password1": new_one, "new_password2": new_one}
    )
    person.refresh_from_db()
    assert person.check_password(new_one)


def test_demo_account_gets_no_email(client, person, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    person.demo = True
    person.save(update_fields=["demo"])
    client.post(reverse("account:recover"), {"email": "pessoa@example.com"})
    assert mail.outbox == []


# --- Required by the clinic (decision 112) ----------------------------------------------------


@pytest.fixture
def required(clinic_a):
    clinic_a.require_two_factor = True
    clinic_a.save(update_fields=["require_two_factor"])
    return clinic_a


def test_records_or_finance_users_are_led_to_activate(
    client, required, create_user, create_practitioner
):
    practitioner = create_user("prof_exigida", required, Role.PRACTITIONER)
    create_practitioner(required, "Dra. Fictícia", user=practitioner)
    finance_user = create_user("fin_exigida", required, Role.FINANCE)
    for user in (practitioner, finance_user):
        client.force_login(user)
        response = client.get(reverse("patients:list"))
        assert response.url == reverse("account:two_factor"), user
        page = client.get(reverse("account:two_factor")).content.decode()
        assert "A clínica exige a verificação em duas etapas" in page
        assert client.get(reverse("account:active")).status_code == 204  # still allowed
        enable_two_factor(user)
        assert client.get(reverse("patients:list")).status_code == 200


def test_reception_and_demo_are_not_required(client, required, create_user):
    reception = create_user("rec_exigida", required, Role.FRONT_DESK)
    client.force_login(reception)
    assert client.get(reverse("patients:list")).status_code == 200
    demo = create_user("demo_exigida", required, Role.ADMIN)
    demo.demo = True
    demo.save(update_fields=["demo"])
    client.force_login(demo)
    assert client.get(reverse("patients:list")).status_code == 200


def test_required_cannot_be_deactivated(client, required, create_user):
    admin = create_user("admin_exigida", required, Role.ADMIN)
    admin.set_password(PASSWORD)
    admin.save()
    device, _ = enable_two_factor(admin)
    client.force_login(admin)
    page = client.get(reverse("account:two_factor")).content.decode()
    assert "não pode ser desativada" in page
    client.post(
        reverse("account:two_factor"),
        {
            "action": "desativar",
            "disable-password": PASSWORD,
            "disable-code": current_code(device),
        },
    )
    assert services.active_for(admin)


def test_without_requirement_nobody_is_led(client, clinic_a, create_user):
    client.force_login(create_user("fin_livre", clinic_a, Role.FINANCE))
    assert client.get(reverse("finance:receivables")).status_code == 200


def test_new_clinic_starts_requiring_and_existing_was_turned_on(django_user_model, client):
    import importlib

    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    from apps.core.models import Clinic

    super_user = django_user_model.objects.create_superuser("instalador_t", "i@example.com", "x")
    client.force_login(super_user)
    client.post(reverse("register_clinic"), {"name": "Clínica Fictícia Nova", "area": "medicine"})
    assert Clinic.single().require_two_factor
    Clinic.objects.update(require_two_factor=False)
    # The migration runs with the models as they were then (Clinica, before decision 157), on
    # the table of the time: a view gives today's table its old name and column (decision 179).
    state_ = MigrationLoader(connection).project_state(("core", "0013_exigir_duas_etapas")).apps
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE VIEW core_clinica AS "
            "SELECT id, require_two_factor AS exigir_duas_etapas FROM core_clinic"
        )
    importlib.import_module("apps.core.migrations.0013_exigir_duas_etapas").ligar(state_, None)
    with connection.cursor() as cursor:
        cursor.execute("DROP VIEW core_clinica")
    assert Clinic.single().require_two_factor


def test_account_tables_go_back_to_conta_and_account_data_is_copied():
    """Decision 154: while the app ran as "account", its data went to account_* tables. The
    migration ran on the tables of the time (conta_*, renamed by decision 179): the test builds
    them as they were."""
    import importlib

    from django.db import connection

    migration = importlib.import_module("apps.account.migrations.0002_back_from_account_tables")
    column_names = {
        "duasetapas": "id serial PRIMARY KEY, usuario_id bigint, segredo text, ativa boolean,"
        " ativada_em timestamptz, ultimo_passo bigint",
        "codigorecuperacao": "id serial PRIMARY KEY, usuario_id bigint, resumo text,"
        " usado_em timestamptz",
    }
    with connection.cursor() as cursor:
        for table, definition in column_names.items():
            cursor.execute(f"CREATE TABLE conta_{table} ({definition})")
    # An installation that never ran as "account" has no such tables: nothing to do.
    with connection.schema_editor() as editor:
        migration.copiar(None, editor)

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO conta_duasetapas (usuario_id, segredo, ativa, ultimo_passo) "
            "VALUES (2, 'ORIGINAL', true, 0)"
        )
        cursor.execute(
            "INSERT INTO conta_codigorecuperacao (usuario_id, resumo) VALUES (2, 'original')"
        )
        for table, definition in column_names.items():
            cursor.execute(f"CREATE TABLE account_{table} ({definition})")
        for user, secret in ((1, "NOVO"), (2, "OUTRO")):
            cursor.execute(
                "INSERT INTO account_duasetapas (usuario_id, segredo, ativa, ultimo_passo) "
                "VALUES (%s, %s, true, 0)",
                [user, secret],
            )
            cursor.execute(
                "INSERT INTO account_codigorecuperacao (usuario_id, resumo) VALUES (%s, %s)",
                [user, f"codigo-{secret}"],
            )
    with connection.schema_editor() as editor:
        migration.copiar(None, editor)

    # Saved only in account_*: copied. Already in conta_*: kept as it was.
    with connection.cursor() as cursor:
        cursor.execute("SELECT usuario_id, segredo FROM conta_duasetapas ORDER BY usuario_id")
        assert cursor.fetchall() == [(1, "NOVO"), (2, "ORIGINAL")]
        cursor.execute("SELECT usuario_id, resumo FROM conta_codigorecuperacao ORDER BY usuario_id")
        assert cursor.fetchall() == [(1, "codigo-NOVO"), (2, "original")]


def test_account_leftovers_are_removed_and_the_app_stays(django_user_model):
    """Decision 158: the leftover account_* tables and content types go; the app's own stay.
    Since decision 194 "account" is the app's label: its migration rows are its own and stay."""
    import importlib

    from django.apps import apps
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from django.db import connection

    migration = importlib.import_module("apps.account.migrations.0005_remove_account_leftovers")
    # An installation that never ran as "account": nothing there, nothing fails.
    with connection.schema_editor() as editor:
        migration.remover(apps, editor)

    user = django_user_model.objects.create_user("com_duas_etapas", password="x")
    TwoFactor.objects.create(user=user, secret="FICA", active=True)
    new_ones = {"duasetapas": "account_two_factor", "codigorecuperacao": "account_recovery_code"}
    with connection.cursor() as cursor:
        for table in ("duasetapas", "codigorecuperacao"):
            cursor.execute(f"CREATE TABLE account_{table} (LIKE {new_ones[table]})")
        cursor.execute(
            "INSERT INTO django_migrations (app, name, applied) "
            "VALUES ('account', '0001_initial', now())"
        )
    kind = ContentType.objects.create(app_label="account", model="duasetapas")
    Permission.objects.create(content_type=kind, codename="view_duasetapas", name="x")

    with connection.schema_editor() as editor:
        migration.remover(apps, editor)

    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'account'")
        [(rows,)] = cursor.fetchall()
    assert not {"account_duasetapas", "account_codigorecuperacao"} & tables
    assert rows > 1  # the app's own migrations, recorded under its label
    assert not ContentType.objects.filter(app_label="account", model="duasetapas").exists()
    assert not Permission.objects.filter(codename="view_duasetapas").exists()
    assert TwoFactor.objects.get(user=user).secret == "FICA"
    assert ContentType.objects.filter(app_label="account", model="twofactor").exists()
