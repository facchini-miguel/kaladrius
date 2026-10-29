import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel, Vinculo
from apps.profissionais.models import Profissional
from apps.prontuario.models import Anexo, Atendimento

from .test_prontuario import ANAMNESE, PNG

SENHAS = {"senha_recepcao": "demo-recepcao-1", "senha_profissional": "demo-profissional-1"}


@pytest.fixture
def demonstracao(clinica_a, criar_profissional, monkeypatch):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    call_command("contas_demonstracao", clinica="Clínica A", profissional="Dr. Bruno", **SENHAS)
    return {"clinica": clinica_a, "bruno": bruno}


def entrar(username, senha):
    """Log in through the login page (axes needs a request), failing if the password is wrong."""
    cliente = Client()
    resposta = cliente.post(reverse("login"), {"username": username, "password": senha})
    assert resposta.status_code == 302, resposta.content.decode()[:300]
    return cliente


def test_cria_as_duas_contas_com_os_perfis(demonstracao):
    Usuario = get_user_model()
    recepcao = Usuario.objects.get(username="demo.recepcao")
    profissional = Usuario.objects.get(username="demo.profissional")
    assert recepcao.demonstracao and profissional.demonstracao
    assert not (recepcao.is_staff or recepcao.is_superuser)
    assert Vinculo.objects.get(usuario=recepcao).papel == Papel.RECEPCAO
    assert Vinculo.objects.get(usuario=profissional).papel == Papel.PROFISSIONAL
    with usar_clinica(demonstracao["clinica"]):
        assert Profissional.objects.get(nome="Dr. Bruno").usuario == profissional
    # Running again resets the passwords and keeps one link per clinic.
    call_command(
        "contas_demonstracao",
        clinica="Clínica A",
        profissional="Dr. Bruno",
        senha_recepcao="outra-1",
        senha_profissional="outra-2",
    )
    assert Vinculo.objects.filter(usuario__username__startswith="demo.").count() == 2
    entrar("demo.recepcao", "outra-1")


def test_recusa_a_senha_dos_dados_de_teste_e_profissional_com_outro_usuario(
    demonstracao, criar_usuario, clinica_a
):
    with pytest.raises(CommandError, match="DJANGO_SEED_PASSWORD"):
        call_command(
            "contas_demonstracao",
            clinica="Clínica A",
            profissional="Dr. Bruno",
            senha_recepcao="semente-secreta",
            senha_profissional="x-1",
        )
    with usar_clinica(clinica_a):
        Profissional.objects.create(nome="Dra. Ana", usuario=criar_usuario("dra.ana"))
    with pytest.raises(CommandError, match="outro usuário"):
        call_command("contas_demonstracao", clinica="Clínica A", profissional="Dra. Ana", **SENHAS)


def test_conta_de_demonstracao_nao_troca_a_senha(demonstracao):
    cliente = entrar("demo.recepcao", SENHAS["senha_recepcao"])
    assert "Trocar senha" not in cliente.get(reverse("inicio")).content.decode()
    resposta = cliente.post(
        reverse("trocar_senha"),
        {
            "old_password": SENHAS["senha_recepcao"],
            "new_password1": "Nova-senha-123!",
            "new_password2": "Nova-senha-123!",
        },
        follow=True,
    )
    assert "Contas de demonstração não trocam a senha." in resposta.content.decode()
    entrar("demo.recepcao", SENHAS["senha_recepcao"])


def test_conta_de_demonstracao_nao_envia_anexos(demonstracao):
    cliente = entrar("demo.profissional", SENHAS["senha_profissional"])
    with usar_clinica(demonstracao["clinica"]):
        from apps.pacientes.models import Paciente

        paciente = Paciente.objects.create(nome="Maria Paciente")
    cliente.post(reverse("prontuario:novo", args=[paciente.pk]), ANAMNESE)
    with usar_clinica(demonstracao["clinica"]):
        atendimento = Atendimento.objects.get()
    pagina = cliente.get(reverse("prontuario:atendimento", args=[atendimento.pk])).content.decode()
    assert "Contas de demonstração não enviam anexos." in pagina
    assert "anexo_enviar" not in pagina and 'enctype="multipart/form-data"' not in pagina
    resposta = cliente.post(
        reverse("prontuario:anexo_enviar", args=[atendimento.pk]),
        {"arquivo": SimpleUploadedFile("x.png", PNG)},
        follow=True,
    )
    assert "Contas de demonstração não enviam anexos." in resposta.content.decode()
    with usar_clinica(demonstracao["clinica"]):
        assert not Anexo.objects.exists()
