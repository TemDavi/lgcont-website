import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CEP_RE = re.compile(r"^\d{5}-?\d{3}$")
DOCUMENTO_RE = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$|^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")


def validar_email(valor):
    email = (valor or "").strip().lower()
    return email if EMAIL_RE.match(email) else None


def validar_documento(valor, obrigatorio=False):
    documento = (valor or "").strip()
    if not documento:
        return None if not obrigatorio else False
    return documento if DOCUMENTO_RE.match(documento) else False


def validar_cep(valor):
    cep = (valor or "").strip()
    if not cep:
        return None
    return cep if CEP_RE.match(cep) else False


def validar_estado(valor):
    estado = (valor or "").strip().upper()
    if not estado:
        return None
    return estado if len(estado) == 2 and estado.isalpha() else False
