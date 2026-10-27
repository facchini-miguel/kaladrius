import datetime

from django import forms
from django.urls import reverse

from apps.core.forms import FormularioBootstrap
from apps.core.validadores import cnpj_valido, cpf_valido, normalizar_cnpj, somente_digitos
from apps.referencias.models import UF, Cidade

from .models import Paciente


class UFField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.sigla} - {obj.nome}"


class CidadeField(forms.ModelChoiceField):
    """City select labeled by name only (the state is chosen in the field beside it)."""

    def label_from_instance(self, obj):
        return obj.nome


def _campo_texto(label, max_length, **attrs):
    """Optional text field that accepts punctuation; the value is normalized in clean_*()."""
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=False,
        widget=forms.TextInput(attrs=attrs),
    )


class PacienteForm(FormularioBootstrap, forms.ModelForm):
    uf = UFField(queryset=UF.objects.all(), required=False, label="UF")
    cidade = CidadeField(queryset=Cidade.objects.none(), required=False, label="Cidade")
    # Typed with punctuation (up to 18 characters), stored as digits/letters only.
    cpf_cnpj = _campo_texto("CPF/CNPJ", 18)
    cep = _campo_texto("CEP", 9, inputmode="numeric")
    telefone_celular = _campo_texto("Celular", 16, inputmode="tel")
    telefone_residencial = _campo_texto("Telefone residencial", 16, inputmode="tel")
    telefone_comercial = _campo_texto("Telefone comercial", 16, inputmode="tel")

    class Meta:
        model = Paciente
        fields = [
            "tipo",
            "nome",
            "razao_social",
            "cpf_cnpj",
            "inscricao_estadual",
            "rg",
            "sexo",
            "data_nascimento",
            "estado_civil",
            "profissao",
            "responsavel",
            "telefone_celular",
            "telefone_residencial",
            "telefone_comercial",
            "email",
            "cep",
            "uf",
            "cidade",
            "bairro",
            "logradouro",
            "numero",
            "complemento",
            "observacoes",
            "ativo",
        ]
        widgets = {
            "tipo": forms.RadioSelect,
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica

        # Chained selects: the city list depends on the chosen state (HTMX).
        self.fields["uf"].widget.attrs.update(
            {
                "hx-get": reverse("referencias:opcoes_cidades"),
                "hx-target": "#id_cidade",
                "hx-trigger": "change",
            }
        )
        uf_id = self.data.get(self.add_prefix("uf")) if self.is_bound else self.instance.uf_id
        self.fields["cidade"].queryset = (
            Cidade.objects.filter(uf_id=int(uf_id))
            if str(uf_id or "").isdecimal()
            else Cidade.objects.none()
        )

    def clean_cpf_cnpj(self):
        # Normalized here; validated in clean() because it depends on the person type.
        return normalizar_cnpj(self.cleaned_data.get("cpf_cnpj", ""))

    def clean_cep(self):
        cep = somente_digitos(self.cleaned_data.get("cep"))
        if cep and len(cep) != 8:
            raise forms.ValidationError("O CEP deve ter 8 dígitos.")
        return cep

    def _limpar_telefone(self, nome):
        telefone = somente_digitos(self.cleaned_data.get(nome))
        if telefone and len(telefone) not in (10, 11):
            raise forms.ValidationError("Informe o DDD e o número (10 ou 11 dígitos).")
        return telefone

    def clean_telefone_celular(self):
        return self._limpar_telefone("telefone_celular")

    def clean_telefone_residencial(self):
        return self._limpar_telefone("telefone_residencial")

    def clean_telefone_comercial(self):
        return self._limpar_telefone("telefone_comercial")

    def clean_data_nascimento(self):
        data = self.cleaned_data.get("data_nascimento")
        if data and data > datetime.date.today():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
        return data

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo")
        documento = dados.get("cpf_cnpj", "")

        if documento:
            if tipo == Paciente.Tipo.FISICA and not cpf_valido(documento):
                self.add_error("cpf_cnpj", "CPF inválido.")
            elif tipo == Paciente.Tipo.JURIDICA and not cnpj_valido(documento):
                self.add_error("cpf_cnpj", "CNPJ inválido.")
            else:
                # The clinic is not a form field, so the unique constraint is checked here.
                outro = (
                    Paciente.objects.filter(cpf_cnpj=documento).exclude(pk=self.instance.pk).first()
                )
                if outro is not None and outro.arquivado:
                    self.add_error(
                        "cpf_cnpj",
                        "Este CPF/CNPJ é de um paciente arquivado. Peça ao administrador da "
                        "clínica para restaurá-lo.",
                    )
                elif outro is not None:
                    self.add_error(
                        "cpf_cnpj", "Já existe um paciente com este CPF/CNPJ nesta clínica."
                    )

        # Fields that only make sense for one person type are cleared for the other.
        if tipo == Paciente.Tipo.JURIDICA:
            for campo in ["rg", "sexo", "estado_civil", "profissao", "responsavel"]:
                dados[campo] = None if campo == "estado_civil" else ""
            dados["data_nascimento"] = None
        else:
            dados["razao_social"] = ""
            dados["inscricao_estadual"] = ""

        cidade, uf = dados.get("cidade"), dados.get("uf")
        if cidade is not None and cidade.uf_id != getattr(uf, "pk", None):
            self.add_error("cidade", "A cidade não pertence à UF escolhida.")
        return dados
