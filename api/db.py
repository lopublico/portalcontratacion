"""
capa de acceso a datos
lee contratos.parquet via duckdb — solo lectura
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ruta al parquet, configurable via .env
PARQUET = os.getenv(
    "PARQUET_PATH",
    str(Path(__file__).parent.parent / "etl" / "data" / "processed" / "contratos.parquet"),
)


def parquet_disponible() -> bool:
    return Path(PARQUET).exists()


def _filas(sql: str, params: Optional[list] = None) -> List[Dict]:
    """ejecuta sql y devuelve lista de dicts"""
    with duckdb.connect() as conn:
        df = conn.execute(sql, params or []).df()
    # reemplazar NaN por None para que json lo serialice como null
    df = df.where(pd.notna(df), None)
    return df.to_dict("records")


def _escalar(sql: str, params: Optional[list] = None):
    """ejecuta sql que devuelve un solo valor"""
    with duckdb.connect() as conn:
        return conn.execute(sql, params or []).fetchone()[0]


# --- contratos ---

_ORDENES_SQL = {
    "fecha_desc":       "fecha_adjudicacion DESC NULLS LAST",
    "fecha_asc":        "TRY_CAST(fecha_adjudicacion AS DATE) ASC NULLS LAST",
    "importe_desc":     "importe_adjudicacion_sin_iva DESC NULLS LAST",
    "importe_asc":      "importe_adjudicacion_sin_iva ASC NULLS LAST",
    "presupuesto_desc": "presupuesto_sin_iva DESC NULLS LAST",
}


def listar_contratos(
    tipo, q, organismo_nif, organismo_id, adjudicatario_nif, adjudicatario_q,
    tipo_contrato, anno, cpv, estado, pyme, importe_min, importe_max,
    fecha_desde, fecha_hasta, tipo_procedimiento, orden, pagina, por_pagina,
) -> Dict:
    condiciones = []
    params: list = []

    if tipo:
        condiciones.append("tipo = ?")
        params.append(tipo)
    if q:
        condiciones.append("(titulo ILIKE ? OR objeto ILIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if organismo_nif:
        condiciones.append("organo_nif = ?")
        params.append(organismo_nif)
    if organismo_id:
        condiciones.append("organo_id_plataforma = ?")
        params.append(organismo_id)
    if adjudicatario_nif:
        condiciones.append("adjudicatario_nif = ?")
        params.append(adjudicatario_nif)
    if adjudicatario_q:
        condiciones.append("adjudicatario_nombre ILIKE ?")
        params.append(f"%{adjudicatario_q}%")
    if tipo_contrato:
        condiciones.append("tipo_contrato = ?")
        params.append(tipo_contrato)
    if anno:
        condiciones.append("YEAR(TRY_CAST(fecha_adjudicacion AS DATE)) = ?")
        params.append(anno)
    if cpv:
        condiciones.append("list_contains(codigos_cpv, ?)")
        params.append(cpv)
    if estado:
        condiciones.append("estado = ?")
        params.append(estado)
    if pyme is not None:
        condiciones.append("adjudicado_pyme = ?")
        params.append(pyme)
    if importe_min is not None:
        condiciones.append("importe_adjudicacion_sin_iva >= ?")
        params.append(importe_min)
    if importe_max is not None:
        condiciones.append("importe_adjudicacion_sin_iva <= ?")
        params.append(importe_max)
    if fecha_desde:
        condiciones.append("TRY_CAST(fecha_adjudicacion AS DATE) >= TRY_CAST(? AS DATE)")
        params.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("TRY_CAST(fecha_adjudicacion AS DATE) <= TRY_CAST(? AS DATE)")
        params.append(fecha_hasta)
    if tipo_procedimiento:
        condiciones.append("tipo_procedimiento = ?")
        params.append(tipo_procedimiento)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    order_sql = _ORDENES_SQL.get(orden or "fecha_desc", _ORDENES_SQL["fecha_desc"])
    offset = (pagina - 1) * por_pagina

    total = _escalar(f"SELECT COUNT(*) FROM read_parquet('{PARQUET}') {where}", params or None)

    registros = _filas(f"""
        SELECT
            tipo, num_expediente, titulo, objeto, estado,
            organo_nombre, organo_nif, organo_id_plataforma,
            tipo_contrato, tipo_procedimiento,
            presupuesto_sin_iva, importe_adjudicacion_sin_iva,
            adjudicatario_nombre, adjudicatario_nif,
            fecha_adjudicacion, fecha_publicacion, codigos_cpv,
            medio_propio_nombre, organo_encomendante_nombre
        FROM read_parquet('{PARQUET}')
        {where}
        ORDER BY {order_sql}
        LIMIT {por_pagina} OFFSET {offset}
    """, params or None)

    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, (total + por_pagina - 1) // por_pagina),
        "resultados": registros,
    }


def obtener_contrato(num_expediente: str) -> List[Dict]:
    return _filas(
        f"SELECT * FROM read_parquet('{PARQUET}') WHERE num_expediente = ?",
        [num_expediente],
    )


# --- organismos ---

def listar_organismos(q: Optional[str], tipo: Optional[str], limit: int, offset: int) -> Dict:
    condiciones = ["organo_id_plataforma IS NOT NULL", "organo_nombre IS NOT NULL"]
    params: list = []

    if q:
        condiciones.append("organo_nombre ILIKE ?")
        params.append(f"%{q}%")
    if tipo:
        condiciones.append(f"tipo = '{tipo}'")

    where = "WHERE " + " AND ".join(condiciones)

    total = _escalar(
        f"SELECT COUNT(DISTINCT organo_id_plataforma) FROM read_parquet('{PARQUET}') {where}",
        params or None,
    )

    registros = _filas(f"""
        SELECT
            organo_id_plataforma, organo_nombre, organo_nif, organo_dir3, organo_tipo,
            COUNT(*) AS num_contratos,
            SUM(importe_adjudicacion_sin_iva) AS total_adjudicado,
            MIN(TRY_CAST(fecha_adjudicacion AS DATE)) AS primer_contrato,
            MAX(TRY_CAST(fecha_adjudicacion AS DATE)) AS ultimo_contrato
        FROM read_parquet('{PARQUET}')
        {where}
        GROUP BY organo_id_plataforma, organo_nombre, organo_nif, organo_dir3, organo_tipo
        ORDER BY num_contratos DESC
        LIMIT {limit} OFFSET {offset}
    """, params or None)

    return {"total": total, "resultados": registros}


def perfil_organismo(id_plataforma: str) -> Optional[Dict]:
    base = f"FROM read_parquet('{PARQUET}') WHERE organo_id_plataforma = ?"

    resumen = _filas(f"""
        SELECT
            organo_id_plataforma, organo_nombre, organo_nif, organo_dir3,
            organo_tipo, organo_ciudad, organo_perfil_url,
            COUNT(*) AS num_contratos,
            SUM(importe_adjudicacion_sin_iva) AS total_adjudicado,
            AVG(importe_adjudicacion_sin_iva) AS importe_medio,
            MIN(TRY_CAST(fecha_adjudicacion AS DATE)) AS primer_contrato,
            MAX(TRY_CAST(fecha_adjudicacion AS DATE)) AS ultimo_contrato
        {base}
        GROUP BY organo_id_plataforma, organo_nombre, organo_nif, organo_dir3,
                 organo_tipo, organo_ciudad, organo_perfil_url
    """, [id_plataforma])

    if not resumen:
        return None

    por_tipo = _filas(f"""
        SELECT tipo, COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base}
        GROUP BY tipo ORDER BY num_contratos DESC
    """, [id_plataforma])

    por_anno = _filas(f"""
        SELECT YEAR(TRY_CAST(fecha_adjudicacion AS DATE)) AS anno,
               COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base} AND fecha_adjudicacion IS NOT NULL
        GROUP BY anno ORDER BY anno
    """, [id_plataforma])

    # pendiente: num_adjudicatarios distintos — de momento no sale en el perfil

    principales_adjudicatarios = _filas(f"""
        SELECT adjudicatario_nombre, adjudicatario_nif,
               COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base} AND adjudicatario_nombre IS NOT NULL
        GROUP BY adjudicatario_nombre, adjudicatario_nif
        ORDER BY total_adjudicado DESC NULLS LAST
        LIMIT 20
    """, [id_plataforma])

    ultimos_contratos = _filas(f"""
        SELECT tipo, num_expediente, titulo, objeto, estado,
               tipo_contrato, tipo_procedimiento,
               presupuesto_sin_iva, importe_adjudicacion_sin_iva,
               adjudicatario_nombre, adjudicatario_nif, fecha_adjudicacion
        {base}
        ORDER BY fecha_adjudicacion DESC NULLS LAST
        LIMIT 10
    """, [id_plataforma])

    return {
        **resumen[0],
        "por_tipo": por_tipo,
        "por_anno": por_anno,
        "principales_adjudicatarios": principales_adjudicatarios,
        "ultimos_contratos": ultimos_contratos,
    }


# --- adjudicatarios ---

def buscar_adjudicatarios(q: Optional[str], limit: int, offset: int) -> Dict:
    where = "WHERE adjudicatario_id IS NOT NULL AND adjudicatario_nombre IS NOT NULL"
    params: list = []
    if q:
        where += " AND adjudicatario_nombre ILIKE ?"
        params.append(f"%{q}%")

    total = _escalar(
        f"SELECT COUNT(DISTINCT adjudicatario_id) FROM read_parquet('{PARQUET}') {where}",
        params or None,
    )

    registros = _filas(f"""
        SELECT
            mode(adjudicatario_nombre) AS adjudicatario_nombre,
            adjudicatario_id,
            mode(adjudicatario_nif) AS adjudicatario_nif,
            mode(adjudicatario_id_tipo) AS adjudicatario_id_tipo,
            COUNT(*) AS num_contratos,
            SUM(importe_adjudicacion_sin_iva) AS total_adjudicado,
            MIN(TRY_CAST(fecha_adjudicacion AS DATE)) AS primer_contrato,
            MAX(TRY_CAST(fecha_adjudicacion AS DATE)) AS ultimo_contrato
        FROM read_parquet('{PARQUET}')
        {where}
        GROUP BY adjudicatario_id
        ORDER BY total_adjudicado DESC NULLS LAST
        LIMIT {limit} OFFSET {offset}
    """, params or None)

    return {"total": total, "resultados": registros}


def perfil_adjudicatario(id: str) -> Optional[Dict]:
    base = f"FROM read_parquet('{PARQUET}') WHERE adjudicatario_id = ?"

    resumen = _filas(f"""
        SELECT
            mode(adjudicatario_nombre) AS adjudicatario_nombre,
            adjudicatario_id,
            mode(adjudicatario_nif) AS adjudicatario_nif,
            mode(adjudicatario_id_tipo) AS adjudicatario_id_tipo,
            mode(adjudicatario_pais) AS adjudicatario_pais,
            COUNT(*) AS num_contratos,
            SUM(importe_adjudicacion_sin_iva) AS total_adjudicado,
            AVG(importe_adjudicacion_sin_iva) AS importe_medio,
            MIN(TRY_CAST(fecha_adjudicacion AS DATE)) AS primer_contrato,
            MAX(TRY_CAST(fecha_adjudicacion AS DATE)) AS ultimo_contrato
        {base}
        GROUP BY adjudicatario_id
    """, [id])

    if not resumen:
        return None

    # falta añadir num_organismos distintos aqui

    por_tipo = _filas(f"""
        SELECT tipo, COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base}
        GROUP BY tipo ORDER BY total_adjudicado DESC NULLS LAST
    """, [id])

    por_anno = _filas(f"""
        SELECT YEAR(TRY_CAST(fecha_adjudicacion AS DATE)) AS anno,
               COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base} AND fecha_adjudicacion IS NOT NULL
        GROUP BY anno ORDER BY anno
    """, [id])

    principales_organismos = _filas(f"""
        SELECT organo_nombre, organo_nif, organo_id_plataforma,
               COUNT(*) AS num_contratos, SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        {base}
        GROUP BY organo_nombre, organo_nif, organo_id_plataforma
        ORDER BY total_adjudicado DESC NULLS LAST
        LIMIT 20
    """, [id])

    return {
        **resumen[0],
        "por_tipo": por_tipo,
        "por_anno": por_anno,
        "principales_organismos": principales_organismos,
    }


# --- estadisticas ---

def estadisticas_generales(tipo: Optional[str]) -> Dict:
    # 1=1 evita tener que ramificar el WHERE segun haya filtro o no
    cond = f"tipo = '{tipo}'" if tipo else "1=1"

    # los encargos no tienen importe_adjudicacion_sin_iva; usan el campo 'importe' del feed ATOM
    # sin el COALESCE aparecen con total_adjudicado null aunque tienen importe real
    por_tipo = _filas(f"""
        SELECT tipo, COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE {cond}
        GROUP BY tipo ORDER BY num_contratos DESC
    """)

    top_organismos = _filas(f"""
        SELECT organo_nombre, organo_id_plataforma,
               COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE {cond} AND organo_nombre IS NOT NULL
        GROUP BY organo_nombre, organo_id_plataforma
        ORDER BY total_adjudicado DESC NULLS LAST LIMIT 5
    """)

    # agrupamos por nif en vez de por id interno — el nif es el identificador publico
    # que usamos para construir la url del perfil en el portal
    top_adjudicatarios = _filas(f"""
        SELECT mode(adjudicatario_nombre) AS adjudicatario_nombre,
               mode(adjudicatario_nif) AS adjudicatario_nif,
               COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE {cond} AND adjudicatario_nif IS NOT NULL
        GROUP BY adjudicatario_nif
        ORDER BY total_adjudicado DESC NULLS LAST LIMIT 5
    """)

    total = _escalar(f"SELECT COUNT(*) FROM read_parquet('{PARQUET}') WHERE {cond}")

    pyme = _filas(f"""
        SELECT adjudicado_pyme, COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE {cond} AND adjudicado_pyme IS NOT NULL
        GROUP BY adjudicado_pyme
    """)

    return {
        "total": total,
        "por_tipo": por_tipo,
        "top_organismos": top_organismos,
        "top_adjudicatarios": top_adjudicatarios,
        "pyme": pyme,
    }


def estadisticas_por_anno(tipo: Optional[str]) -> List[Dict]:
    cond = f"AND tipo = '{tipo}'" if tipo else ""
    # tipo en el GROUP BY permite filtrar la serie temporal por licitaciones/menores/encargos
    # sin el, el portal solo puede mostrar el agregado global
    return _filas(f"""
        SELECT YEAR(TRY_CAST(fecha_adjudicacion AS DATE)) AS anno,
               tipo,
               COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE fecha_adjudicacion IS NOT NULL {cond}
        GROUP BY anno, tipo ORDER BY anno, tipo
    """)


def estadisticas_por_mes(tipo: Optional[str], anno: int) -> List[Dict]:
    cond = f"AND tipo = '{tipo}'" if tipo else ""
    return _filas(f"""
        SELECT MONTH(TRY_CAST(fecha_adjudicacion AS DATE)) AS mes,
               COUNT(*) AS num_contratos,
               SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE YEAR(TRY_CAST(fecha_adjudicacion AS DATE)) = {anno}
          AND fecha_adjudicacion IS NOT NULL {cond}
        GROUP BY mes ORDER BY mes
    """)


def estadisticas_cpv(tipo: Optional[str], limit: int) -> List[Dict]:
    cond = f"AND tipo = '{tipo}'" if tipo else ""
    # unnest expande el array de cpv para poder agrupar por codigo individual
    return _filas(f"""
        SELECT unnest(codigos_cpv) AS cpv,
               COUNT(*) AS num_contratos,
               SUM(importe_adjudicacion_sin_iva) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE codigos_cpv IS NOT NULL {cond}
        GROUP BY cpv ORDER BY num_contratos DESC
        LIMIT {limit}
    """)


def sectores_cpv() -> List[Dict]:
    # los CPV tienen 8 digitos; los dos primeros identifican la division (categoria grande)
    # estadisticas_cpv() devuelve codigos completos — esta funcion agrupa a nivel de division
    # para el grafico de sectores del dashboard, donde los codigos completos son demasiado granulares
    return _filas(f"""
        SELECT SUBSTR(cpv, 1, 2) AS division, COUNT(*) AS num_contratos
        FROM (
            SELECT UNNEST(codigos_cpv) AS cpv
            FROM read_parquet('{PARQUET}')
            WHERE codigos_cpv IS NOT NULL
        )
        GROUP BY division
        ORDER BY num_contratos DESC
    """)


def estadisticas_tipo_contrato() -> List[Dict]:
    # tipo_contrato es el codigo CODICE: 1=Obras, 2=Servicios, 3=Suministros...
    # el portal lo usa para el grafico de barras horizontales del dashboard
    return _filas(f"""
        SELECT tipo_contrato,
               COUNT(*) AS num_contratos,
               SUM(COALESCE(importe_adjudicacion_sin_iva, importe)) AS total_adjudicado
        FROM read_parquet('{PARQUET}')
        WHERE tipo_contrato IS NOT NULL
        GROUP BY tipo_contrato
        ORDER BY num_contratos DESC
    """)
