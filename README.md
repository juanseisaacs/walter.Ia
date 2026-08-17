# RBH Tutor

Tutor AI adaptativo para niños de 1° a 5° de primaria en **lectura, escritura y
aritmética**.

Enseña con **método socrático**: guía con preguntas y pistas escalonadas, y
**nunca regala la respuesta**. Conoce al niño y crece con él sesión a sesión.

> Nace del RFS **"The Primer"** de Y Combinator (Fall 2026), inspirado en el
> Primer de *The Diamond Age*.

---

## Los 4 criterios

Toda decisión se justifica contra uno de estos. Si una feature no sirve a
ninguno, no entra al MVP.

1. **Curriculum fidelity** — grafo de habilidades anclado a DBA (Colombia) y
   Core Knowledge
2. **Safety** — vigilante independiente del tutor, dos caminos a la alarma
3. **Longitudinal memory** — ficha del niño consolidada, con decaimiento
4. **Parent trust** — auditoría del método en el 100% de las sesiones

**Ayudamos con la tarea; nunca la hacemos.** La tarea es materia prima para
tutoría, no un problema a resolver.

---

## Arranque

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ".[dev]"

cp .env.example .env            # y completar las llaves

pytest                          # tests rápidos, sin red
```

---

## Mapa del repo

| Carpeta | Qué hay |
|---|---|
| `knowledge/` | **El activo.** Currículum y prompts. Versionado, revisable en PR |
| `src/tutor/` | El código. 10 archivos, 5 de ellos puros |
| `evals/` | Suite organizada en los 4 criterios de YC |
| `scripts/` | Herramientas de construcción (banco de ejercicios) |
| `data/` | Runtime. Nunca se versiona — contiene datos de menores |

---

## Documentos

- **`ARCHITECTURE.md`** — las decisiones y su razón. La memoria del proyecto
- **`CLAUDE.md`** — reglas duras y convenciones

---

## Estado

**Fase 0 completa** — estructura y contratos, sin lógica.
Próximo: fase 1 (loader y validador del grafo).

Plan completo en `ARCHITECTURE.md` §15.
