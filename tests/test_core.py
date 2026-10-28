import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


def test_inicio_exige_login(client):
    resposta = client.get(reverse("inicio"))
    assert resposta.status_code == 302
    assert reverse("login") in resposta.url


def test_login_e_inicio(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    resposta = client.post(
        reverse("login"), {"username": "maria", "password": "senha-de-teste-123"}, follow=True
    )
    assert resposta.status_code == 200
    assert ", maria" in resposta.content.decode()


def test_rodape_mostra_autor_e_versao(client):
    conteudo = client.get(reverse("login")).content.decode()
    assert "Desenvolvido por Miguel Facchini" in conteudo
    assert "versão" in conteudo


def test_login_com_senha_errada(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    resposta = client.post(reverse("login"), {"username": "maria", "password": "errada"})
    assert resposta.status_code == 200
    assert "Usuário ou senha incorretos" in resposta.content.decode()


def test_senha_usa_argon2(django_user_model):
    usuario = django_user_model.objects.create_user(username="joao", password="senha-de-teste-123")
    assert usuario.password.startswith("argon2")


def test_criar_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("criar_admin")
    admin = get_user_model().objects.get(username="admin")
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password("senha-forte-de-teste-123")

    # Running it again changes nothing
    call_command("criar_admin")
    assert get_user_model().objects.filter(username="admin").count() == 1


def test_criar_admin_sem_senha(monkeypatch):
    monkeypatch.delenv("DJANGO_ADMIN_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("criar_admin")


def test_logout_exige_post(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    assert client.get(reverse("logout")).status_code == 405
    client.post(reverse("logout"))
    assert client.get(reverse("inicio")).status_code == 302


def test_usuario_troca_a_propria_senha(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    assert "Trocar senha" in client.get(reverse("inicio")).content.decode()
    resposta = client.post(
        reverse("trocar_senha"),
        {
            "old_password": "senha-de-teste-123",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
        follow=True,
    )
    assert "Senha alterada." in resposta.content.decode()
    usuario.refresh_from_db()
    assert usuario.check_password("outra-senha-forte-456")
    # The session stays open after the change.
    assert client.get(reverse("inicio")).status_code == 200


def test_troca_de_senha_exige_a_senha_atual(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    resposta = client.post(
        reverse("trocar_senha"),
        {
            "old_password": "errada",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
    )
    assert resposta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.check_password("senha-de-teste-123")


def test_sem_recuperacao_de_senha_por_email(client):
    # No e-mail is configured, so the reset pages would never deliver anything.
    assert client.get("/conta/password_reset/").status_code == 404


def test_aviso_de_backup_atrasado_so_para_superusuario(client, django_user_model, settings):
    import datetime

    from django.utils import timezone

    from apps.core.models import Backup

    admin = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    comum = django_user_model.objects.create_user("ana", password="senha-de-teste-123")
    client.force_login(admin)
    # Development has no backups: no warning.
    settings.BACKUP_MONITORADO = False
    assert "backup" not in client.get(reverse("inicio")).content.decode()
    # A server where no backup was ever recorded warns too.
    settings.BACKUP_MONITORADO = True
    assert "Nenhum backup do banco foi registrado" in client.get(reverse("inicio")).content.decode()

    call_command("registrar_backup", "medical-system-x.dump", "1024")
    assert Backup.objects.get().tamanho == 1024
    assert "backups diários pararam" not in client.get(reverse("inicio")).content.decode()

    Backup.objects.update(momento=timezone.now() - datetime.timedelta(hours=27))
    assert "backups diários pararam" in client.get(reverse("inicio")).content.decode()
    client.force_login(comum)
    assert "backups diários pararam" not in client.get(reverse("inicio")).content.decode()


# --- Clinic settings ---------------------------------------------------------------


def dados_clinica(**extra):
    return {
        "nome": "Clínica Atualizada",
        "documento": "",
        "email": "",
        "telefone": "",
        "agenda_inicio": "08:00",
        "agenda_fim": "18:00",
        "agenda_intervalo": 30,
        **extra,
    }


def test_admin_altera_configuracoes_da_clinica(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    assert "Configurações da clínica" in cliente.get(reverse("inicio")).content.decode()
    assert 'value="07:30"' in cliente.get(reverse("configuracoes")).content.decode()
    resposta = cliente.post(
        reverse("configuracoes"), dados_clinica(documento="11.222.333/0001-81", agenda_intervalo=15)
    )
    assert resposta.status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.nome, clinica_a.documento) == ("Clínica Atualizada", "11222333000181")
    assert (clinica_a.agenda_inicio, clinica_a.agenda_intervalo) == (datetime.time(8), 15)


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_o_admin_altera_configuracoes(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    assert cliente.get(reverse("configuracoes")).status_code == 403


@pytest.mark.parametrize(
    ("extra", "erro"),
    [
        ({"agenda_inicio": "18:00", "agenda_fim": "08:00"}, "depois do início"),
        ({"documento": "123"}, "CPF/CNPJ inválido"),
        ({"agenda_inicio": "10:00"}, "ficaria fora do novo horário"),  # 09:00 appointment
        ({"agenda_intervalo": 60, "agenda_inicio": "08:30"}, "ficaria fora"),  # misaligned
    ],
)
def test_configuracoes_invalidas(extra, erro, clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        profissional = Profissional.objects.create(nome="Dra. Teste")
        tipo = TipoAtendimento.objects.first()
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        inicio = timezone.make_aware(datetime.datetime.combine(amanha, datetime.time(9)))
        Agendamento.objects.create(
            profissional=profissional,
            tipo=tipo,
            inicio=inicio,
            fim=inicio + datetime.timedelta(hours=1),
        )
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    resposta = cliente.post(reverse("configuracoes"), dados_clinica(**extra))
    assert resposta.status_code == 200
    assert erro in resposta.content.decode()
