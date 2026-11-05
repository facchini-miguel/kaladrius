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
    codigos = services.ativar(dispositivo)
    return dispositivo, codigos


def codigo_atual(dispositivo, deslocamento=0):
    totp = pyotp.TOTP(dispositivo.secret)
    return totp.at(time.time() + deslocamento * totp.interval)


# --- Idle time and the eye button ----------------------------------------------------------


def test_sessao_termina_com_30_minutos_sem_uso(client, pessoa):
    assert settings.SESSION_COOKIE_AGE == 30 * 60 and settings.SESSION_SAVE_EVERY_REQUEST
    client.force_login(pessoa)
    page = client.get(reverse("home")).content.decode()
    assert 'data-inatividade="30"' in page and reverse("account:active") in page
    assert client.get(reverse("account:active")).status_code == 204
    saiu = client.get(reverse("login"), {"inatividade": "1"})
    assert "30 minutos sem uso" in saiu.content.decode()


def test_ativo_sem_login_vai_para_o_login(client):
    assert client.get(reverse("account:active")).status_code == 302


def test_campos_de_senha_ganham_o_olhinho(client):
    page = client.get(reverse("login")).content.decode()
    assert 'data-mostrar-senha="Mostrar a senha"' in page


# --- Wrong logins per address ---------------------------------------------------------------


def test_muitas_tentativas_do_mesmo_endereco_bloqueiam_qualquer_usuario(client, pessoa):
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


def test_poucas_tentativas_do_endereco_nao_bloqueiam(client, pessoa):
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


def test_ativar_com_qr_code(client, pessoa):
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


def test_login_pede_o_codigo_depois_da_senha(client, pessoa):
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


def test_codigo_de_recuperacao_vale_uma_vez(client, pessoa):
    _, codigos = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    assert client.post(reverse("account:code"), {"code": codigos[0].lower()}).status_code == 302
    client.logout()
    entrar(client, pessoa)
    segunda = client.post(reverse("account:code"), {"code": codigos[0]})
    assert "Código incorreto" in segunda.content.decode()


def test_cinco_codigos_errados_voltam_ao_login(client, pessoa):
    ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    for _ in range(5):
        client.post(reverse("account:code"), {"code": "000000"})
    # Like 5 wrong passwords: the login protection locks the user for an hour.
    assert client.get(reverse("account:code")).url == reverse("login")
    bloqueado = entrar(client, pessoa)
    assert "_auth_user_id" not in client.session and bloqueado.status_code != 302


def test_passo_do_codigo_expira(client, pessoa):
    dispositivo, _ = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    session = client.session
    session["duas_etapas_pendente"]["momento"] -= 10 * 60
    session.save()
    assert client.post(reverse("account:code"), {"code": codigo_atual(dispositivo)}).url == (
        reverse("login")
    )


def test_desativar_e_gerar_novos_codigos(client, pessoa):
    dispositivo, antigos = ligar_duas_etapas(pessoa)
    client.force_login(pessoa)
    novos = client.post(
        reverse("account:two_factor"),
        {"acao": "codigos", "codigos-code": codigo_atual(dispositivo)},
    )
    assert "Códigos de recuperação" in novos.content.decode()
    assert not services.verificar_recuperacao(pessoa, antigos[1])  # old ones stop working
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
    assert response.status_code == 302 and not services.ativa_para(pessoa)


def test_administrador_remove_a_verificacao_de_quem_perdeu_o_celular(
    client, clinica_a, pessoa, criar_usuario
):
    ligar_duas_etapas(pessoa)
    admin = criar_usuario("admin_conta", clinica_a, Role.ADMIN)
    client.force_login(admin)
    vinculo = pessoa.vinculos.get()
    page = client.get(reverse("team:edit", args=[vinculo.pk])).content.decode()
    assert "Remover a verificação em duas etapas" in page
    client.post(reverse("team:two_factor", args=[vinculo.pk]))
    assert not services.ativa_para(pessoa)
    assert AuditEntry.objects.filter(object_repr__contains="removida").exists()


def test_conta_de_demonstracao_nao_ativa(client, pessoa):
    pessoa.demo = True
    pessoa.save(update_fields=["demo"])
    client.force_login(pessoa)
    assert client.get(reverse("account:two_factor")).status_code == 302
    assert not TwoFactor.objects.exists()


# --- Password recovery by e-mail -------------------------------------------------------------


def test_sem_email_configurado_nao_ha_recuperacao(client, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = False
    assert client.get(reverse("account:recover")).status_code == 404
    assert "Esqueci minha senha" not in client.get(reverse("login")).content.decode()


def test_recuperar_senha_por_email(client, pessoa, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = True
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


def test_conta_de_demonstracao_nao_recebe_email(client, pessoa, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = True
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


def test_quem_acessa_prontuario_ou_financeiro_e_levado_a_ativar(
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


def test_recepcao_e_demonstracao_nao_sao_obrigadas(client, exigida, criar_usuario):
    reception = criar_usuario("rec_exigida", exigida, Role.FRONT_DESK)
    client.force_login(reception)
    assert client.get(reverse("patients:list")).status_code == 200
    demo = criar_usuario("demo_exigida", exigida, Role.ADMIN)
    demo.demo = True
    demo.save(update_fields=["demo"])
    client.force_login(demo)
    assert client.get(reverse("patients:list")).status_code == 200


def test_obrigatoria_nao_pode_ser_desativada(client, exigida, criar_usuario):
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
    assert services.ativa_para(admin)


def test_sem_exigencia_ninguem_e_levado(client, clinica_a, criar_usuario):
    client.force_login(criar_usuario("fin_livre", clinica_a, Role.FINANCE))
    assert client.get(reverse("finance:receivables")).status_code == 200


def test_clinica_nova_comeca_exigindo_e_a_existente_foi_ligada(django_user_model, client):
    import importlib

    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    from apps.core.models import Clinic

    super_usuario = django_user_model.objects.create_superuser("instalador_t", "i@example.com", "x")
    client.force_login(super_usuario)
    client.post(reverse("register_clinic"), {"name": "Clínica Fictícia Nova", "area": "medicina"})
    assert Clinic.single().require_two_factor
    Clinic.objects.update(require_two_factor=False)
    # The migration runs with the models as they were then (Clinica, before decision 157).
    estado = MigrationLoader(connection).project_state(("core", "0013_exigir_duas_etapas")).apps
    importlib.import_module("apps.core.migrations.0013_exigir_duas_etapas").ligar(estado, None)
    assert Clinic.single().require_two_factor


def test_tabelas_da_conta_voltam_a_ser_as_conta_e_o_que_foi_salvo_nas_account_e_copiado(
    django_user_model,
):
    """Decision 154: while the app ran as "account", its data went to account_* tables."""
    import importlib

    from django.db import connection

    migracao = importlib.import_module("apps.account.migrations.0002_back_from_account_tables")
    assert TwoFactor._meta.db_table == "conta_duasetapas"
    assert RecoveryCode._meta.db_table == "conta_codigorecuperacao"

    # An installation that never ran as "account" has no such tables: nothing to do.
    with connection.schema_editor() as editor:
        migracao.copiar(None, editor)

    so_na_account = django_user_model.objects.create_user("so_na_account", password="x")
    nas_duas = django_user_model.objects.create_user("nas_duas", password="x")
    TwoFactor.objects.create(user=nas_duas, secret="ORIGINAL", active=True)
    RecoveryCode.objects.create(user=nas_duas, digest="original")
    with connection.cursor() as cursor:
        for table in ("duasetapas", "codigorecuperacao"):
            cursor.execute(f"CREATE TABLE account_{table} (LIKE conta_{table} INCLUDING DEFAULTS)")
        for user, secret in ((so_na_account, "NOVO"), (nas_duas, "OUTRO")):
            cursor.execute(
                "INSERT INTO account_duasetapas (id, usuario_id, segredo, ativa, ultimo_passo) "
                "VALUES (%s, %s, %s, true, 0)",
                [user.pk + 1000, user.pk, secret],
            )
            cursor.execute(
                "INSERT INTO account_codigorecuperacao (id, usuario_id, resumo) "
                "VALUES (%s, %s, %s)",
                [user.pk + 1000, user.pk, f"codigo-{secret}"],
            )
    with connection.schema_editor() as editor:
        migracao.copiar(None, editor)

    # Saved only in account_*: copied. Already in conta_*: kept as it was.
    assert TwoFactor.objects.get(user=so_na_account).secret == "NOVO"
    assert TwoFactor.objects.get(user=nas_duas).secret == "ORIGINAL"
    assert list(
        RecoveryCode.objects.filter(user=so_na_account).values_list("digest", flat=True)
    ) == ["codigo-NOVO"]
    assert list(RecoveryCode.objects.filter(user=nas_duas).values_list("digest", flat=True)) == [
        "original"
    ]


def test_sobras_da_account_sao_removidas_e_a_conta_fica(django_user_model):
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
    with connection.cursor() as cursor:
        for table in ("duasetapas", "codigorecuperacao"):
            cursor.execute(f"CREATE TABLE account_{table} (LIKE conta_{table})")
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
