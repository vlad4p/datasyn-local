"""Extraer entidades (empresas y personas) de boletin_sa_constitucion.

Usage: uv run python scripts/python/extraer_entidades.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

# Patrones de extracción de personas
PATRON_CAPS = re.compile(
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]*)*"
    r"\s+[A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]{3,})?)"
    r"\s*(?:\([^)]*\))?\s*[,;]"
)

PATRON_MIXTO = re.compile(
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+?)"
    r"\s*,\s*(?:DNI\b|argentino|argentina|uruguayo|venezolano)"
)

# Filtro de falsos positivos
STOPLIST = {
    "SOCIOS", "ACCIONISTAS", "ADUANAS", "AFIP",
    "BUENOS AIRES", "PROVINCIA", "ESTATUTOS", "EXTRANJERO",
    "INGENIERO", "COUNTRY", "PUNTA", "BARRIO", "PAIS",
}


def es_valido(nombre: str) -> bool:
    if len(nombre) >= 60:
        return False
    upper = nombre.upper()
    for stop in STOPLIST:
        if stop in upper:
            return False
    return True


def extraer_personas(contenido: str) -> set[str]:
    """Extraer nombres de personas del contenido estructurado."""
    # Limitar al texto antes de "OBJETO" para evitar firmas y objetos sociales
    idx = contenido.find("OBJETO")
    if idx > 0:
        contenido = contenido[:idx]

    personas = set()
    for patron in (PATRON_CAPS, PATRON_MIXTO):
        for m in patron.finditer(contenido):
            nombre = m.group(1).strip()
            if es_valido(nombre):
                personas.add(nombre)
    return personas


def main():
    con = db.connect()
    try:
        # Limpiar tablas para regenerar
        con.execute("DELETE FROM entidad_vinculos")
        con.execute("DELETE FROM entidades.entidades")
        con.execute("DROP SEQUENCE IF EXISTS entidades_seq")
        con.execute("CREATE SEQUENCE entidades_seq START 1")

        # 1. Empresas de TODOS los días
        rows = con.sql(
            "SELECT id, titulo, contenido FROM bronze.boletin_sa_constitucion ORDER BY id"
        ).fetchall()

        seq_start = 1

        empresas = []
        personas_raw = []
        for aviso_id, titulo, contenido in rows:
            empresas.append((titulo, "empresa"))
            for p in extraer_personas(contenido):
                personas_raw.append((p, "persona", aviso_id))

        # Insertar empresas (deduplicadas)
        vistas_emp = set()
        for nombre, tipo in empresas:
            if nombre in vistas_emp:
                continue
            vistas_emp.add(nombre)
            try:
                con.execute(
                    "INSERT INTO entidades.entidades (id, nombre, tipo) VALUES (?, ?, ?)",
                    [seq_start, nombre, tipo],
                )
                seq_start += 1
            except Exception as e:
                print(f"  ⚠ Error insertando empresa {nombre}: {e}")

        print(f"✅ Empresas insertadas: {len(vistas_emp)}")

        # Insertar personas (deduplicadas)
        vistas = set()
        for nombre, tipo, aviso_id in personas_raw:
            if nombre in vistas:
                continue
            vistas.add(nombre)
            try:
                con.execute(
                    "INSERT INTO entidades.entidades (id, nombre, tipo) "
                    "VALUES (?, ?, ?)",
                    [seq_start, nombre, tipo],
                )
                seq_start += 1
            except Exception as e:
                print(f"  ⚠ Error insertando persona {nombre}: {e}")

        print(f"✅ Personas insertadas: {len(vistas)}")

        # 3. Vínculos: entidad → aviso
        # Obtener mapping nombre → id
        entidades_map = {}
        for eid, ename, etype in con.sql(
            "SELECT id, nombre, tipo FROM entidades.entidades"
        ).fetchall():
            entidades_map[(ename, etype)] = eid

        # Vincular empresas a su aviso
        vinculados = 0
        for aviso_id, titulo in con.sql(
            "SELECT id, titulo FROM bronze.boletin_sa_constitucion ORDER BY id"
        ).fetchall():
            key = (titulo, "empresa")
            if key in entidades_map:
                eid = entidades_map[key]
                try:
                    con.execute(
                        "INSERT INTO entidad_vinculos (entidad_id, aviso_id, rol) "
                        "VALUES (?, ?, 'empresa_constituida') "
                        "ON CONFLICT (entidad_id, aviso_id) DO NOTHING",
                        [eid, aviso_id],
                    )
                    vinculados += 1
                except Exception as e:
                    print(f"  ⚠ Error vinculando {titulo}: {e}")

        # Vincular personas a su aviso
        for nombre, tipo, aviso_id in personas_raw:
            key = (nombre, "persona")
            if key in entidades_map:
                eid = entidades_map[key]
                try:
                    con.execute(
                        "INSERT INTO entidad_vinculos (entidad_id, aviso_id, rol) "
                        "VALUES (?, ?, 'socio') "
                        "ON CONFLICT (entidad_id, aviso_id) DO NOTHING",
                        [eid, aviso_id],
                    )
                except Exception:
                    pass  # ya existe

        print(f"✅ Vínculos creados: {vinculados} empresas + personas")

        # Mostrar resumen
        print()
        res = con.sql(
            "SELECT tipo, COUNT(*) AS cantidad FROM entidades.entidades GROUP BY tipo ORDER BY tipo"
        ).fetchall()
        for tipo, cant in res:
            print(f"  {tipo}: {cant}")
        print(f"  Total: {sum(c for _, c in res)}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
