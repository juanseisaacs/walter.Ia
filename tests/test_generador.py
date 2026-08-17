"""Tests del validador de ejercicios.

Generar es fácil; validar es lo que importa. Un ejercicio con la cuenta mal
que llega a un niño destruye la confianza del papá para siempre — y los
modelos se equivocan en aritmética.
"""

import pytest

from scripts.build_exercise_bank import evaluar_cuenta, validar

# ─────────────────────────────────────────────────────────────────────────────
# Evaluación segura
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "expresion,esperado",
    [("27 + 15", 42), ("100 - 37", 63), ("7 * 8", 56), ("84 / 4", 21), ("(2 + 3) * 4", 20)],
)
def test_evalua_aritmetica_simple(expresion, esperado):
    assert evaluar_cuenta(expresion) == esperado


@pytest.mark.parametrize(
    "peligroso",
    [
        "__import__('os').system('dir')",
        "open('/etc/passwd').read()",
        "[].__class__.__mro__",
        "exec('print(1)')",
    ],
)
def test_no_ejecuta_codigo(peligroso):
    """La expresión viene de un MODELO. No se usa eval: se camina el AST y solo
    se permiten números y las cuatro operaciones."""
    assert evaluar_cuenta(peligroso) is None


def test_una_expresion_rota_no_revienta():
    assert evaluar_cuenta("27 +") is None
    assert evaluar_cuenta("hola") is None
    assert evaluar_cuenta("") is None


# ─────────────────────────────────────────────────────────────────────────────
# Validación de ejercicios
# ─────────────────────────────────────────────────────────────────────────────


def test_acepta_un_ejercicio_correcto():
    enunciado = "Juan tiene 27 figuritas y le regalan 15. Cuantas tiene?"
    assert validar(enunciado, "42", "27 + 15") is None


def test_RECHAZA_cuando_la_cuenta_no_cierra():
    """EL CASO QUE JUSTIFICA TODO ESTO. El modelo dice que 27+15 da 41."""
    motivo = validar("Juan tiene 27 y le dan 15", "41", "27 + 15")
    assert motivo is not None
    assert "NO CIERRA" in motivo


def test_rechaza_enunciado_vacio():
    assert validar("", "42", "27 + 15") is not None


def test_rechaza_respuesta_vacia():
    assert validar("Cuanto es 27 mas 15?", "", "27 + 15") is not None


def test_rechaza_lo_muy_largo_para_escuchar():
    """El niño lo ESCUCHA. Si no se entiende de una, no sirve."""
    largo = "Juan fue a la tienda y compro cosas. " * 10
    assert "escuchar" in validar(largo, "42", "27 + 15")


def test_acepta_sin_cuenta_cuando_no_la_hay():
    """Comparar u ordenar no tienen una cuenta que verificar."""
    assert validar("Que numero es mayor: 45 o 54?", "54", None) is None


def test_rechaza_si_hay_cuenta_pero_la_respuesta_no_es_numero():
    motivo = validar("Cuanto es 27 mas 15?", "muchas", "27 + 15")
    assert "no es un número" in motivo


def test_acepta_coma_decimal():
    assert validar("Cuanto es 9 dividido 2?", "4,5", "9 / 2") is None
