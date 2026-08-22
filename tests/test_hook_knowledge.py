"""El hook que valida `knowledge/` después de editarlo.

Un hook es código que corre solo, sin nadie mirando. Si deja de funcionar, no
falla nada visible: simplemente se deja de validar y nos enteramos semanas
después, cuando el currículum roto llega a la sesión de un niño. Es el patrón
de `BITACORA.md` con otra cara.

Por eso se prueban las dos mitades: que el script decida bien, y que el
`settings.json` siga apuntando a un script que existe.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from hook_validar_knowledge import (  # noqa: E402
    SUITES,
    EntradaIlegible,
    ruta_editada,
    suite_para,
)

RAIZ = Path(__file__).resolve().parent.parent
SETTINGS = RAIZ / ".claude" / "settings.json"


# ─────────────────────────────────────────────────────────────────────────────
# Qué se valida y qué no
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ruta,suite_esperada",
    [
        # Windows manda backslashes; Git Bash, barras. Las dos tienen que andar:
        # la primera versión solo contemplaba una y el hook no disparaba nunca.
        (r"C:\RBH-Tutor\knowledge\curriculum\matematicas.yaml", "tests/test_curriculum.py"),
        ("C:/RBH-Tutor/knowledge/curriculum/schema.json", "tests/test_curriculum.py"),
        (r"C:\RBH-Tutor\knowledge\prompts\valores.es.md", "tests/test_voice.py"),
        ("/c/RBH-Tutor/knowledge/prompts/vigilante.es.md", "tests/test_voice.py"),
    ],
)
def test_cada_carpeta_de_knowledge_tiene_quien_la_valide(ruta: str, suite_esperada: str):
    elegida = suite_para(ruta)
    assert elegida is not None, f"{ruta} quedó sin validador"
    assert elegida[0] == suite_esperada


@pytest.mark.parametrize(
    "ruta",
    ["C:/RBH-Tutor/src/tutor/api.py", "C:/RBH-Tutor/README.md", "web/src/App.tsx"],
)
def test_lo_que_no_es_knowledge_no_dispara_nada(ruta: str):
    """Un hook que corre en cada edición del repo es un hook que se desactiva."""
    assert suite_para(ruta) is None


def test_las_suites_que_dispara_el_hook_existen():
    """Si alguien renombra un archivo de tests, el hook queda apuntando al vacío
    y `pytest` sale con error de colección — o peor, en verde sin recolectar."""
    for _, suite, _ in SUITES:
        assert (RAIZ / suite).exists(), f"el hook apunta a {suite}, que no existe"


# ─────────────────────────────────────────────────────────────────────────────
# La entrada
# ─────────────────────────────────────────────────────────────────────────────


def test_lee_la_ruta_de_las_dos_formas_del_payload():
    edit = json.dumps({"tool_input": {"file_path": "a/b.yaml"}})
    write = json.dumps({"tool_response": {"filePath": "c/d.md"}})
    assert ruta_editada(edit) == "a/b.yaml"
    assert ruta_editada(write) == "c/d.md"


def test_una_entrada_ilegible_no_se_traga_en_silencio():
    """LA prueba de este archivo.

    La primera versión devolvía cadena vacía ante un JSON roto, `main()` salía 0
    y el hook **aprobaba sin haber validado nada**. Se descubrió probándolo, no
    escribiéndolo: el `echo` de la prueba se comía los escapes y el hook decía
    que todo estaba bien con el currículum deliberadamente roto.
    """
    with pytest.raises(EntradaIlegible):
        ruta_editada("no soy json")
    with pytest.raises(EntradaIlegible):
        ruta_editada("[1, 2, 3]")


# ─────────────────────────────────────────────────────────────────────────────
# El contrato con .claude/settings.json
# ─────────────────────────────────────────────────────────────────────────────


def test_el_settings_llama_a_un_script_que_existe():
    """Mismo antipatrón que `test_contrato_pizarra`: algo declarado de un lado
    y consumido del otro. Si el script se renombra, el hook deja de correr y
    nada avisa."""
    assert SETTINGS.exists(), ".claude/settings.json desapareció: el hook no corre"
    config = json.loads(SETTINGS.read_text(encoding="utf-8"))

    comandos = [
        h["command"]
        for grupo in config["hooks"]["PostToolUse"]
        for h in grupo["hooks"]
        if h.get("type") == "command"
    ]
    assert comandos, "el hook de PostToolUse se quedó sin comando"

    modulo = "scripts.hook_validar_knowledge"
    assert any(modulo in c for c in comandos), (
        f"ningún hook invoca {modulo}. Si se renombró el script, "
        f"actualizá .claude/settings.json — el hook está muerto hasta entonces."
    )
    assert (RAIZ / "scripts" / "hook_validar_knowledge.py").exists()


def test_los_datos_de_menores_no_se_pueden_editar_por_accidente():
    """`data/` tiene transcripciones de niños. Leer se pregunta; escribir, no."""
    config = json.loads(SETTINGS.read_text(encoding="utf-8"))
    deny = config["permissions"]["deny"]
    assert "Edit(data/**)" in deny
    assert "Read(.env)" in deny and "Edit(.env)" in deny


# ─────────────────────────────────────────────────────────────────────────────
# De punta a punta
# ─────────────────────────────────────────────────────────────────────────────


def test_el_hook_corre_entero_y_aprueba_lo_que_esta_sano():
    """Entra por donde entra el hook: proceso nuevo, JSON por stdin.

    No comprueba solo la decisión — comprueba que el script arranca, encuentra
    `pytest`, corre la suite y vuelve. Un `ImportError` acá saldría en verde en
    cualquier test que importara las funciones sueltas.
    """
    editado = RAIZ / "knowledge" / "prompts" / "valores.es.md"
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(editado)}})
    p = subprocess.run(
        [sys.executable, "-m", "scripts.hook_validar_knowledge"],
        input=payload,
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert p.returncode == 0, f"el hook rechazó prompts sanos:\n{p.stdout}\n{p.stderr}"
