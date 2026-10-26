from django.core.validators import RegexValidator

validar_cor = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use uma cor no formato #RRGGBB.")
