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
SENHA = "Senha-Ficticia-2026!"


@pytest.fixture
def pessoa(clinica_a, criar_usuario):
    user = criar_usuario("pessoa_conta", clinica_a, Role.FRONT_DESK)
    user.set_password(SENHA)
    user.email = "pessoa@example.com"
    user.save()
    return user


def entrar(client, user, password=SENHA, proximo=""):
    data = {"username": user.username, "password": password}
    if proximo:
        data["next"] = proximo
    return client.post(reverse("login"), data)


def ligar_duas_etapas(user):
    dispositivo = services.prepare(user)
    codigos = services.activate(dispositivo)
    return dispositivo, codigos


def codigo_atual(dispositivo, deslocamento=0):
    totp = pyotp.TOTP(dispositivo.secret)
    return totp.at(time.time() + deslocamento * totp.interval)


# --- Idle time and the eye button ----------------------------------------------------------


def test_session_ends_after_30_idle_minutes(client, pessoa):
    assert settings.SESSION_COOKIE_AGE == 30 * 60 and settings.SESSION_SAVE_EVERY_REQUEST
    client.force_login(pessoa)
    page = client.get(reverse("home")).content.decode()
    assert 'data-idle-minutes="30"' in page and reverse("account:active") in page
    assert client.get(reverse("account:active")).status_code == 204
    saiu = client.get(reverse("login"), {"inatividade": "1"})
    assert "30 minutos sem uso" in saiu.content.decode()


def test_active_without_login_goes_to_login(client):
    assert client.get(reverse("account:active")).status_code == 302


def test_password_fields_get_the_eye_toggle(client):
    page = client.get(reverse("login")).content.decode()
    assert 'data-show-password="Mostrar a senha"' in page


# --- Wrong logins per address ---------------------------------------------------------------


def test_many_attempts_from_one_address_block_any_user(client, pessoa):
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
    response = entrar(client, pessoa)
    assert response.status_code == 200
    assert "Muitas tentativas erradas a partir deste endereço" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_few_attempts_from_the_address_do_not_block(client, pessoa):
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
    assert entrar(client, pessoa).status_code == 302


# --- Two-step verification --------------------------------------------------------------------


def test_activate_with_qr_code(client, pessoa):
    client.force_login(pessoa)
    page = client.get(reverse("account:two_factor")).content.decode()
    assert "<svg" in page and "otpauth" not in page  # the secret is in the QR, not text
    dispositivo = TwoFactor.objects.get(user=pessoa)
    errado = client.post(reverse("account:two_factor"), {"acao": "ativar", "code": "000000"})
    assert "Código incorreto" in errado.content.decode()
    response = client.post(
        reverse("account:two_factor"), {"acao": "ativar", "code": codigo_atual(dispositivo)}
    )
    text = response.content.decode()
    assert "Verificação em duas etapas ativada" in text
    assert RecoveryCode.objects.filter(user=pessoa).count() == 10
    assert AuditEntry.objects.filter(object_repr__contains="ativada").exists()
    dispositivo.refresh_from_db()
    assert dispositivo.active and dispositivo.secret not in text


def test_login_asks_for_the_code_after_the_password(client, pessoa):
    dispositivo, _ = ligar_duas_etapas(pessoa)
    response = entrar(client, pessoa, proximo=reverse("patients:list"))
    assert response.url == reverse("account:code")
    assert "_auth_user_id" not in client.session  # not logged in yet
    errado = client.post(reverse("account:code"), {"code": "123456"})
    assert "Código incorreto" in errado.content.decode()
    assert AccessAttempt.objects.filter(username=pessoa.username).exists()  # counted
    code = codigo_atual(dispositivo)
    certo = client.post(reverse("account:code"), {"code": code})
    assert certo.url == reverse("patients:list")
    assert client.session["_auth_user_id"] == str(pessoa.pk)
    # The same code does not work twice.
    client.logout()
    entrar(client, pessoa)
    repetido = client.post(reverse("account:code"), {"code": code})
    assert "Código incorreto" in repetido.content.decode()


def test_recovery_code_works_once(client, pessoa):
    _, codigos = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    assert client.post(reverse("account:code"), {"code": codigos[0].lower()}).status_code == 302
    client.logout()
    entrar(client, pessoa)
    segunda = client.post(reverse("account:code"), {"code": codigos[0]})
    assert "Código incorreto" in segunda.content.decode()


def test_five_wrong_codes_return_to_login(client, pessoa):
    ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    for _ in range(5):
        client.post(reverse("account:code"), {"code": "000000"})
    # Like 5 wrong passwords: the login protection locks the user for an hour.
    assert client.get(reverse("account:code")).url == reverse("login")
    bloqueado = entrar(client, pessoa)
    assert "_auth_user_id" not in client.session and bloqueado.status_code != 302


def test_code_step_expires(client, pessoa):
    dispositivo, _ = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    session = client.session
    session["duas_etapas_pendente"]["momento"] -= 10 * 60
    session.save()
    assert client.post(reverse("account:code"), {"code": codigo_atual(dispositivo)}).url == (
        reverse("login")
    )


def test_deactivate_and_generate_new_codes(client, pessoa):
    dispositivo, antigos = ligar_duas_etapas(pessoa)
    client.force_login(pessoa)
    novos = client.post(
        reverse("account:two_factor"),
        {"acao": "codigos", "codigos-code": codigo_atual(dispositivo)},
    )
    assert "Códigos de recuperação" in novos.content.decode()
    assert not services.verify_recovery(pessoa, antigos[1])  # old ones stop working
    errado = client.post(
        reverse("account:two_factor"),
        {"acao": "desativar", "desativar-senha": "errada", "desativar-code": "000000"},
    )
    assert "Senha incorreta" in errado.content.decode()
    response = client.post(
        reverse("account:two_factor"),
        {
            "acao": "desativar",
            "desativar-senha": SENHA,
            "desativar-code": codigo_atual(dispositivo, deslocamento=1),
        },
    )
    assert response.status_code == 302 and not services.active_for(pessoa)


def test_admin_removes_verification_of_who_lost_the_phone(client, clinica_a, pessoa, criar_usuario):
    ligar_duas_etapas(pessoa)
    admin = criar_usuario("admin_conta", clinica_a, Role.ADMIN)
    client.force_login(admin)
    vinculo = pessoa.vinculos.get()
    page = client.get(reverse("team:edit", args=[vinculo.pk])).content.decode()
    assert "Remover a verificação em duas etapas" in page
    client.post(reverse("team:two_factor", args=[vinculo.pk]))
    assert not services.active_for(pessoa)
    assert AuditEntry.objects.filter(object_repr__contains="removida").exists()


def test_demo_account_does_not_activate(client, pessoa):
    pessoa.demo = True
    pessoa.save(update_fields=["demo"])
    client.force_login(pessoa)
    assert client.get(reverse("account:two_factor")).status_code == 302
    assert not TwoFactor.objects.exists()


# --- Password recovery by e-mail -------------------------------------------------------------


def test_no_email_configured_means_no_recovery(client, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = False
    assert client.get(reverse("account:recover")).status_code == 404
    assert "Esqueci minha senha" not in client.get(reverse("login")).content.decode()


def test_recover_password_by_email(client, pessoa, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    assert "Esqueci minha senha" in client.get(reverse("login")).content.decode()
    response = client.post(reverse("account:recover"), {"email": "pessoa@example.com"})
    assert response.url == reverse("account:recovery_sent")
    [message] = mail.outbox
    assert "pessoa_conta" in message.body and "Kaladrius" in message.subject
    link = next(row for row in message.body.splitlines() if "/account/password/new/" in row)
    path = link.split("testserver", 1)[1]
    formulario = client.get(path, follow=True)
    nova = "Nova-Senha-Ficticia-77"
    client.post(formulario.redirect_chain[-1][0], {"new_password1": nova, "new_password2": nova})
    pessoa.refresh_from_db()
    assert pessoa.check_password(nova)


def test_demo_account_gets_no_email(client, pessoa, settings):
    settings.PASSWORD_RECOVERY_BY_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    pessoa.demo = True
    pessoa.save(update_fields=["demo"])
    client.post(reverse("account:recover"), {"email": "pessoa@example.com"})
    assert mail.outbox == []


# --- Required by the clinic (decision 112) ----------------------------------------------------


@pytest.fixture
def exigida(clinica_a):
    clinica_a.require_two_factor = True
    clinica_a.save(update_fields=["require_two_factor"])
    return clinica_a


def test_records_or_finance_users_are_led_to_activate(
    client, exigida, criar_usuario, criar_profissional
):
    practitioner = criar_usuario("prof_exigida", exigida, Role.PRACTITIONER)
    criar_profissional(exigida, "Dra. Fictícia", user=practitioner)
    financeiro = criar_usuario("fin_exigida", exigida, Role.FINANCE)
    for user in (practitioner, financeiro):
        client.force_login(user)
        response = client.get(reverse("patients:list"))
        assert response.url == reverse("account:two_factor"), user
        page = client.get(reverse("account:two_factor")).content.decode()
        assert "A clínica exige a verificação em duas etapas" in page
        assert client.get(reverse("account:active")).status_code == 204  # still allowed
        ligar_duas_etapas(user)
        assert client.get(reverse("patients:list")).status_code == 200


def test_reception_and_demo_are_not_required(client, exigida, criar_usuario):
    reception = criar_usuario("rec_exigida", exigida, Role.FRONT_DESK)
    client.force_login(reception)
    assert client.get(reverse("patients:list")).status_code == 200
    demo = criar_usuario("demo_exigida", exigida, Role.ADMIN)
    demo.demo = True
    demo.save(update_fields=["demo"])
    client.force_login(demo)
    assert client.get(reverse("patients:list")).status_code == 200


def test_required_cannot_be_deactivated(client, exigida, criar_usuario):
    admin = criar_usuario("admin_exigida", exigida, Role.ADMIN)
    admin.set_password(SENHA)
    admin.save()
    dispositivo, _ = ligar_duas_etapas(admin)
    client.force_login(admin)
    page = client.get(reverse("account:two_factor")).content.decode()
    assert "não pode ser desativada" in page
    client.post(
        reverse("account:two_factor"),
        {
            "acao": "desativar",
            "desativar-senha": SENHA,
            "desativar-code": codigo_atual(dispositivo),
        },
    )
    assert services.active_for(admin)


def test_without_requirement_nobody_is_led(client, clinica_a, criar_usuario):
    client.force_login(criar_usuario("fin_livre", clinica_a, Role.FINANCE))
    assert client.get(reverse("finance:receivables")).status_code == 200


def test_new_clinic_starts_requiring_and_existing_was_turned_on(django_user_model, client):
    import importlib

    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    from apps.core.models import Clinic

    super_usuario = django_user_model.objects.create_superuser("instalador_t", "i@example.com", "x")
    client.force_login(super_usuario)
    client.post(reverse("register_clinic"), {"name": "Clínica Fictícia Nova", "area": "medicina"})
    assert Clinic.single().require_two_factor
    Clinic.objects.update(require_two_factor=False)
    # The migration runs with the models as they were then (Clinica, before decision 157), on
    # the table of the time: a view gives today's table its old name and column (decision 179).
    estado = MigrationLoader(connection).project_state(("core", "0013_exigir_duas_etapas")).apps
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE VIEW core_clinica AS "
            "SELECT id, require_two_factor AS exigir_duas_etapas FROM core_clinic"
        )
    importlib.import_module("apps.core.migrations.0013_exigir_duas_etapas").ligar(estado, None)
    with connection.cursor() as cursor:
        cursor.execute("DROP VIEW core_clinica")
    assert Clinic.single().require_two_factor


def test_account_tables_go_back_to_conta_and_account_data_is_copied():
    """Decision 154: while the app ran as "account", its data went to account_* tables. The
    migration ran on the tables of the time (conta_*, renamed by decision 179): the test builds
    them as they were."""
    import importlib

    from django.db import connection

    migracao = importlib.import_module("apps.account.migrations.0002_back_from_account_tables")
    colunas = {
        "duasetapas": "id serial PRIMARY KEY, usuario_id bigint, segredo text, ativa boolean,"
        " ativada_em timestamptz, ultimo_passo bigint",
        "codigorecuperacao": "id serial PRIMARY KEY, usuario_id bigint, resumo text,"
        " usado_em timestamptz",
    }
    with connection.cursor() as cursor:
        for table, definicao in colunas.items():
            cursor.execute(f"CREATE TABLE conta_{table} ({definicao})")
    # An installation that never ran as "account" has no such tables: nothing to do.
    with connection.schema_editor() as editor:
        migracao.copiar(None, editor)

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO conta_duasetapas (usuario_id, segredo, ativa, ultimo_passo) "
            "VALUES (2, 'ORIGINAL', true, 0)"
        )
        cursor.execute(
            "INSERT INTO conta_codigorecuperacao (usuario_id, resumo) VALUES (2, 'original')"
        )
        for table, definicao in colunas.items():
            cursor.execute(f"CREATE TABLE account_{table} ({definicao})")
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
        migracao.copiar(None, editor)

    # Saved only in account_*: copied. Already in conta_*: kept as it was.
    with connection.cursor() as cursor:
        cursor.execute("SELECT usuario_id, segredo FROM conta_duasetapas ORDER BY usuario_id")
        assert cursor.fetchall() == [(1, "NOVO"), (2, "ORIGINAL")]
        cursor.execute("SELECT usuario_id, resumo FROM conta_codigorecuperacao ORDER BY usuario_id")
        assert cursor.fetchall() == [(1, "codigo-NOVO"), (2, "original")]


def test_account_leftovers_are_removed_and_conta_stays(django_user_model):
    """Decision 158: the account_* tables, their migration row and content types go; conta_*
    stays as it is."""
    import importlib

    from django.apps import apps
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from django.db import connection

    migracao = importlib.import_module("apps.account.migrations.0005_remove_account_leftovers")
    # An installation that never ran as "account": nothing there, nothing fails.
    with connection.schema_editor() as editor:
        migracao.remover(apps, editor)

    user = django_user_model.objects.create_user("com_duas_etapas", password="x")
    TwoFactor.objects.create(user=user, secret="FICA", active=True)
    novas = {"duasetapas": "account_two_factor", "codigorecuperacao": "account_recovery_code"}
    with connection.cursor() as cursor:
        for table in ("duasetapas", "codigorecuperacao"):
            cursor.execute(f"CREATE TABLE account_{table} (LIKE {novas[table]})")
        cursor.execute(
            "INSERT INTO django_migrations (app, name, applied) "
            "VALUES ('account', '0001_initial', now())"
        )
    kind = ContentType.objects.create(app_label="account", model="duasetapas")
    Permission.objects.create(content_type=kind, codename="view_duasetapas", name="x")

    with connection.schema_editor() as editor:
        migracao.remover(apps, editor)

    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'account'")
        [(rows,)] = cursor.fetchall()
    assert not {"account_duasetapas", "account_codigorecuperacao"} & tables
    assert rows == 0
    assert not ContentType.objects.filter(app_label="account").exists()
    assert not Permission.objects.filter(codename="view_duasetapas").exists()
    assert TwoFactor.objects.get(user=user).secret == "FICA"
    assert ContentType.objects.filter(app_label="conta", model="twofactor").exists()
