"""
API REST de contratacion publica espanola.
Solo lectura, sin autenticacion.

Arrancar:
    uvicorn main:app --reload

Docs:
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import re

import csv
import io
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import db


_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_ORDENES_VALIDOS = {"fecha_desc", "fecha_asc", "importe_desc", "importe_asc", "presupuesto_desc"}


def _validar_fecha(valor: Optional[str], nombre: str) -> None:
    if valor and not _DATE_RE.match(valor):
        raise HTTPException(status_code=400, detail=f"'{nombre}' debe ser YYYY-MM-DD")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not db.parquet_disponible():
        print(f"parquet no encontrado: {db.PARQUET}")
        print("ejecuta: python ../etl/scripts/procesar.py --parquet")
    yield


_DESCRIPCION = """
Acceso de solo lectura a los contratos del sector público español publicados en
[PLACSP](https://contrataciondelestado.es) (Plataforma de Contratación del Sector Público).

**Tipos de contrato**

| valor | descripción |
|-------|-------------|
| `licitaciones` | Contratos con licitación pública — obras, servicios, suministros |
| `menores` | Adjudicación directa sin licitación (< 15 000 € servicios / < 40 000 € obras) |
| `encargos` | Encargos a medios propios entre entidades públicas |
| `consultas` | Consultas preliminares al mercado, sin importe |

**Estados**

| valor | descripción |
|-------|-------------|
| `PUB` | Publicado |
| `EV` | En evaluación |
| `ADJ` | Adjudicado |
| `RES` | Resuelto |
| `ANUL` | Anulado |
| `DES` | Desistido |

**Importes** — siempre en euros sin IVA.

**Paginación** — todos los listados aceptan `pagina` (desde 1) y `por_pagina` (máx. 100).
"""

app = FastAPI(
    title="Portal de Contratación Pública",
    description=_DESCRIPCION,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

TIPOS_VALIDOS = {"licitaciones", "menores", "encargos", "consultas"}
ESTADOS_VALIDOS = {"PUB", "EV", "ADJ", "RES", "ANUL", "DES"}
EXPORT_CAP = 50_000


def _verificar_datos():
    if not db.parquet_disponible():
        raise HTTPException(status_code=503, detail="Datos no disponibles. Ejecuta procesar.py --parquet")


def _validar_tipo(tipo: Optional[str]):
    if tipo:
        for t in tipo.split(','):
            if t.strip() and t.strip() not in TIPOS_VALIDOS:
                raise HTTPException(status_code=400, detail=f"Tipo no valido. Usa: {', '.join(sorted(TIPOS_VALIDOS))}")


# --- info ---

@app.get("/", tags=["Info"])
def raiz():
    """Estado de la API y tipos disponibles."""
    return {
        "api": "Portal de Contratacion Publica",
        "version": "0.1.0",
        "datos_disponibles": db.parquet_disponible(),
        "tipos": sorted(TIPOS_VALIDOS),
        "docs": "/docs",
    }


# --- estadisticas ---

@app.get("/estadisticas", tags=["Estadísticas"])
def estadisticas(tipo: Optional[str] = Query(None, description="Filtra por tipo de contrato")):
    """
    Resumen global: total de registros, importe adjudicado, top 5 organismos y adjudicatarios,
    distribución por tipo y ratio pyme.

    Sin filtro devuelve todos los tipos agregados. Con `tipo=licitaciones` devuelve solo licitaciones.

    **Ejemplo:** `GET /estadisticas`

    ```json
    {
      "total": 5011898,
      "por_tipo": [
        {"tipo": "menores", "num_contratos": 3397400, "total_adjudicado": 14282324840},
        {"tipo": "licitaciones", "num_contratos": 1598781, "total_adjudicado": 489076237489}
      ],
      "top_organismos": [
        {
          "organo_nombre": "Rectorado de la Universidad de Murcia",
          "organo_id_plataforma": "40812410125001",
          "num_contratos": 86370,
          "total_adjudicado": 167891690
        }
      ],
      "top_adjudicatarios": [...],
      "pyme": [...]
    }
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_generales(tipo)


@app.get("/estadisticas/anual", tags=["Estadísticas"])
def estadisticas_anual(tipo: Optional[str] = Query(None, description="Filtra por tipo de contrato")):
    """
    Serie temporal anual: número de contratos e importe por año y tipo.
    Útil para gráficos de evolución.

    Devuelve una fila por combinación `(anno, tipo)`. Sin filtro incluye todos los tipos;
    agrupa en el cliente si necesitas el total global por año.

    **Ejemplo:** `GET /estadisticas/anual?tipo=licitaciones`

    ```json
    [
      {"anno": 2019, "tipo": "licitaciones", "num_contratos": 98432, "total_adjudicado": 28450000000},
      {"anno": 2020, "tipo": "licitaciones", "num_contratos": 87651, "total_adjudicado": 24100000000}
    ]
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_por_anno(tipo)


@app.get("/estadisticas/mensual", tags=["Estadísticas"])
def estadisticas_mensual(
    tipo: Optional[str] = Query(None, description="Filtra por tipo de contrato"),
    anno: int = Query(default_factory=lambda: datetime.now().year, description="Año a consultar"),
):
    """
    Distribución mensual para un año concreto. Por defecto devuelve el año en curso.

    **Ejemplo:** `GET /estadisticas/mensual?anno=2024`

    ```json
    [
      {"mes": 1, "num_contratos": 8432, "total_adjudicado": 1240000000},
      {"mes": 2, "num_contratos": 7891, "total_adjudicado": 980000000}
    ]
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_por_mes(tipo, anno)


@app.get("/estadisticas/cpv", tags=["Estadísticas"])
def estadisticas_cpv(
    tipo: Optional[str] = Query(None, description="Filtra por tipo de contrato"),
    limit: int = Query(20, ge=1, le=200, description="Número de códigos CPV a devolver"),
):
    """
    Ranking de códigos CPV (vocabulario común de contratos públicos) por número de contratos.

    Los CPV son códigos de 8 dígitos que clasifican el objeto del contrato.
    Un contrato puede tener varios CPV; se cuenta una vez por cada código.

    **Ejemplo:** `GET /estadisticas/cpv?limit=3`

    ```json
    [
      {"cpv": "85000000", "num_contratos": 142300, "total_adjudicado": 8920000000},
      {"cpv": "45000000", "num_contratos": 98100, "total_adjudicado": 34200000000},
      {"cpv": "72000000", "num_contratos": 76400, "total_adjudicado": 5100000000}
    ]
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_cpv(tipo, limit)


@app.get("/estadisticas/sectores-cpv", tags=["Estadísticas"])
def estadisticas_sectores_cpv():
    """
    Agrupa los CPV por sus dos primeros dígitos (división). Devuelve las divisiones ordenadas
    por número de contratos. Usado en el gráfico de sectores del dashboard.

    **Ejemplo:** `GET /estadisticas/sectores-cpv`

    ```json
    [
      {"division": "85", "num_contratos": 142300},
      {"division": "45", "num_contratos": 98100}
    ]
    ```
    """
    _verificar_datos()
    return db.sectores_cpv()


@app.get("/estadisticas/tipo-contrato", tags=["Estadísticas"])
def estadisticas_tipo_contrato():
    """
    Distribución por tipo de contrato CODICE (obras, servicios, suministros...).
    Distinto del campo `tipo` (licitaciones / menores / encargos): este campo
    clasifica el objeto del contrato, no el procedimiento.

    | código | descripción |
    |--------|-------------|
    | 1 | Obras |
    | 2 | Servicios |
    | 3 | Suministros |
    | 4 | Concesión de obras |
    | 5 | Concesión de servicios |

    **Ejemplo:** `GET /estadisticas/tipo-contrato`

    ```json
    [
      {"tipo_contrato": "2", "num_contratos": 980000, "total_adjudicado": 210000000000},
      {"tipo_contrato": "1", "num_contratos": 340000, "total_adjudicado": 180000000000}
    ]
    ```
    """
    _verificar_datos()
    return db.estadisticas_tipo_contrato()


# --- contratos ---

@app.get("/contratos", tags=["Contratos"])
def listar_contratos(
    tipo: Optional[str] = Query(None, description="licitaciones · menores · encargos · consultas"),
    q: Optional[str] = Query(None, description="Texto libre — busca en título y objeto del contrato"),
    organismo_nif: Optional[str] = Query(None, description="NIF del organismo contratante (ej. Q2818029G)"),
    organismo_id: Optional[str] = Query(None, description="ID interno de PLACSP del organismo (ej. 10874020131162)"),
    adjudicatario_nif: Optional[str] = Query(None, description="NIF del adjudicatario (ej. B84498955)"),
    adjudicatario_q: Optional[str] = Query(None, description="Texto libre — busca en el nombre del adjudicatario"),
    tipo_contrato: Optional[str] = Query(None, description="Código CODICE: 1 Obras · 2 Servicios · 3 Suministros · 4 Concesión obras · 5 Concesión servicios"),
    anno: Optional[int] = Query(None, description="Año de adjudicación (ej. 2023)"),
    cpv: Optional[str] = Query(None, description="Código CPV de 8 dígitos (ej. 72000000)"),
    estado: Optional[str] = Query(None, description="PUB · EV · ADJ · RES · ANUL · DES"),
    pyme: Optional[bool] = Query(None, description="true para contratos adjudicados a pymes"),
    importe_min: Optional[float] = Query(None, ge=0, description="Importe mínimo adjudicado sin IVA (€)"),
    importe_max: Optional[float] = Query(None, ge=0, description="Importe máximo adjudicado sin IVA (€)"),
    fecha_desde: Optional[str] = Query(None, description="Fecha de adjudicación desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha de adjudicación hasta (YYYY-MM-DD)"),
    tipo_procedimiento: Optional[str] = Query(None, description="Código de procedimiento (1 abierto · 2 restringido · 3 negociado...)"),
    orden: Optional[str] = Query(None, description="fecha_desc · fecha_asc · importe_desc · importe_asc · presupuesto_desc"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    """
    Listado paginado de contratos con filtros combinables. Todos los filtros son opcionales
    y se aplican con AND. Los importes excluyen contratos con fecha de adjudicación futura.

    **Ejemplo:** `GET /contratos?tipo=licitaciones&q=auditoria&anno=2023&por_pagina=2`

    ```json
    {
      "total": 847,
      "pagina": 1,
      "por_pagina": 2,
      "paginas": 424,
      "resultados": [
        {
          "tipo": "licitaciones",
          "num_expediente": "2023/0006062",
          "titulo": "Servicio de Auditoría externa para la Universidad Carlos III de Madrid",
          "estado": "RES",
          "organo_nombre": "Rector de la Universidad Carlos III de Madrid",
          "organo_nif": "Q2818029G",
          "organo_id_plataforma": "10874020131162",
          "tipo_contrato": "2",
          "tipo_procedimiento": "1",
          "presupuesto_sin_iva": 32000.0,
          "importe_adjudicacion_sin_iva": 21500.0,
          "adjudicatario_nombre": "MAZARS AUDITORES, S.L.P.",
          "adjudicatario_nif": "B61622262",
          "fecha_adjudicacion": "2023-06-14",
          "codigos_cpv": ["79212000"]
        }
      ]
    }
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)

    if estado:
        for e in estado.split(','):
            if e.strip() and e.strip() not in ESTADOS_VALIDOS:
                raise HTTPException(status_code=400, detail=f"Estado no valido. Usa: {', '.join(sorted(ESTADOS_VALIDOS))}")
    if orden and orden not in _ORDENES_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Orden no valido")

    _validar_fecha(fecha_desde, "fecha_desde")
    _validar_fecha(fecha_hasta, "fecha_hasta")

    if importe_min is not None and importe_max is not None and importe_min > importe_max:
        raise HTTPException(status_code=400, detail="importe_min no puede ser mayor que importe_max")
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="fecha_desde no puede ser posterior a fecha_hasta")

    return db.listar_contratos(
        tipo, q, organismo_nif, organismo_id,
        adjudicatario_nif, adjudicatario_q,
        tipo_contrato, anno, cpv, estado, pyme,
        importe_min, importe_max,
        fecha_desde, fecha_hasta,
        tipo_procedimiento, orden,
        pagina, por_pagina,
    )


@app.get("/contratos/exportar", tags=["Contratos"])
def exportar_contratos(
    formato: str = Query(..., description="csv · json · xlsx"),
    tipo: Optional[str] = Query(None, description="Uno o varios separados por coma: licitaciones,menores"),
    q: Optional[str] = Query(None),
    organismo_q: Optional[str] = Query(None),
    adjudicatario_q: Optional[str] = Query(None),
    tipo_contrato: Optional[str] = Query(None, description="Uno o varios separados por coma: 1,2,3"),
    cpv_sector: Optional[str] = Query(None, description="División CPV (2 dígitos), varios separados por coma: 45,72"),
    estado: Optional[str] = Query(None, description="Uno o varios separados por coma: ADJ,RES"),
    importe_min: Optional[float] = Query(None, ge=0),
    importe_max: Optional[float] = Query(None, ge=0),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    orden: Optional[str] = Query(None),
):
    """
    Exporta los contratos que cumplen los filtros activos en el buscador.
    Limitado a {EXPORT_CAP:,} registros. Formatos: `csv`, `json`, `xlsx`.
    """
    _verificar_datos()

    if formato not in ("csv", "json", "xlsx"):
        raise HTTPException(status_code=400, detail="formato debe ser csv, json o xlsx")
    if orden and orden not in _ORDENES_VALIDOS:
        raise HTTPException(status_code=400, detail="orden no válido")
    _validar_fecha(fecha_desde, "fecha_desde")
    _validar_fecha(fecha_hasta, "fecha_hasta")

    def _split(v):
        return [x.strip() for x in v.split(",") if x.strip()] if v else None

    tipos_lista   = _split(tipo)
    estados_lista = _split(estado)
    ctto_lista    = _split(tipo_contrato)
    cpv_lista     = _split(cpv_sector)

    if tipos_lista and not all(t in TIPOS_VALIDOS for t in tipos_lista):
        raise HTTPException(status_code=400, detail="Tipo no válido")
    if estados_lista and not all(e in ESTADOS_VALIDOS for e in estados_lista):
        raise HTTPException(status_code=400, detail="Estado no válido")

    df = db.exportar_contratos(
        tipo=tipos_lista, q=q,
        organismo_q=organismo_q, adjudicatario_q=adjudicatario_q,
        tipo_contrato=ctto_lista, cpv_sector=cpv_lista,
        estado=estados_lista,
        importe_min=importe_min, importe_max=importe_max,
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        orden=orden, limit=EXPORT_CAP,
    )

    if formato == "json":
        content = df.to_json(orient="records", force_ascii=False, date_format="iso")
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=contratos.json"},
        )

    if formato == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),  # utf-8-sig para Excel en Windows
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=contratos.csv"},
        )

    # xlsx
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=contratos.xlsx"},
    )


@app.get("/contratos/atom/{atom_num}", tags=["Contratos"])
def obtener_contrato_por_atom(atom_num: str):
    """
    Busca un contrato por el número final de su identificador Atom de PLACSP.

    El `id_atom` completo tiene la forma
    `https://contrataciondelestado.es/sindicacion/.../13426955`.
    Este endpoint acepta solo el número final (`13426955`).

    **Ejemplo:** `GET /contratos/atom/13426955`

    Devuelve el objeto contrato completo (mismo esquema que `/contratos`).
    """
    _verificar_datos()
    resultado = db.obtener_contrato_por_atom(atom_num)
    if not resultado:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return resultado


@app.get("/contratos/{num_expediente:path}", tags=["Contratos"])
def obtener_contrato(num_expediente: str):
    """
    Devuelve todos los registros con ese número de expediente. Puede haber más de uno
    si el contrato ha pasado por varias fases (publicado → adjudicado → resuelto).

    El número de expediente puede contener barras (`/`), por eso el parámetro
    acepta cualquier path.

    **Ejemplo:** `GET /contratos/2023%2F0006062`

    ```json
    [
      {
        "num_expediente": "2023/0006062",
        "titulo": "Servicio de Auditoría externa para la Universidad Carlos III de Madrid",
        "estado": "RES",
        ...
      }
    ]
    ```
    """
    _verificar_datos()
    resultados = db.obtener_contrato(num_expediente)
    if not resultados:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return resultados


# --- organismos ---

@app.get("/organismos", tags=["Organismos"])
def listar_organismos(
    q: Optional[str] = Query(None, description="Texto libre — busca en el nombre del organismo"),
    tipo: Optional[str] = Query(None, description="Filtra por tipo de contrato publicado"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    """
    Listado de organismos contratantes ordenados por número de contratos.
    Solo incluye organismos con `organo_id_plataforma` (identificador de PLACSP) y nombre conocidos.

    **Ejemplo:** `GET /organismos?q=universidad&por_pagina=2`

    ```json
    {
      "total": 184,
      "pagina": 1,
      "por_pagina": 2,
      "paginas": 92,
      "resultados": [
        {
          "organo_id_plataforma": "40812410125001",
          "organo_nombre": "Rectorado de la Universidad de Murcia",
          "organo_nif": "Q3018001B",
          "num_contratos": 86370,
          "total_adjudicado": 167891690,
          "primer_contrato": "2012-01-10",
          "ultimo_contrato": "2025-11-28"
        }
      ]
    }
    ```
    """
    _verificar_datos()
    _validar_tipo(tipo)
    offset = (pagina - 1) * por_pagina
    resultado = db.listar_organismos(q, tipo, por_pagina, offset)
    return {
        **resultado,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, (resultado["total"] + por_pagina - 1) // por_pagina),
    }


@app.get("/organismos/{id_plataforma}", tags=["Organismos"])
def perfil_organismo(id_plataforma: str):
    """
    Perfil completo de un organismo: resumen agregado, distribución por tipo de contrato,
    evolución anual, top 20 adjudicatarios y últimos 10 contratos.

    El `id_plataforma` es el identificador interno de PLACSP que aparece en los listados
    (`organo_id_plataforma`). No es el NIF ni el código DIR3.

    **Ejemplo:** `GET /organismos/40812410125001`

    ```json
    {
      "organo_id_plataforma": "40812410125001",
      "organo_nombre": "Rectorado de la Universidad de Murcia",
      "organo_nif": "Q3018001B",
      "num_contratos": 86370,
      "total_adjudicado": 167891690,
      "importe_medio": 1944,
      "primer_contrato": "2012-01-10",
      "ultimo_contrato": "2025-11-28",
      "por_tipo": [...],
      "por_anno": [...],
      "principales_adjudicatarios": [...],
      "ultimos_contratos": [...]
    }
    ```
    """
    _verificar_datos()
    resultado = db.perfil_organismo(id_plataforma)
    if not resultado:
        raise HTTPException(status_code=404, detail="Organismo no encontrado")
    return resultado


# --- adjudicatarios ---

@app.get("/adjudicatarios", tags=["Adjudicatarios"])
def listar_adjudicatarios(
    q: Optional[str] = Query(None, description="Texto libre — busca en el nombre del adjudicatario"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    """
    Listado de empresas y personas adjudicatarias ordenadas por importe total recibido.
    Los registros se agrupan por `adjudicatario_id` (NIF normalizado), de modo que variaciones
    en el nombre (`ACME S.L.` / `Acme SL`) aparecen como un único adjudicatario.

    **Ejemplo:** `GET /adjudicatarios?q=fisher`

    ```json
    {
      "total": 3,
      "pagina": 1,
      "por_pagina": 20,
      "paginas": 1,
      "resultados": [
        {
          "adjudicatario_nombre": "FISHER SCIENTIFIC, S.L.",
          "adjudicatario_id": "B84498955",
          "adjudicatario_nif": "B84498955",
          "num_contratos": 11863,
          "total_adjudicado": 30131053,
          "primer_contrato": "2012-03-15",
          "ultimo_contrato": "2025-10-02"
        }
      ]
    }
    ```
    """
    _verificar_datos()
    offset = (pagina - 1) * por_pagina
    resultado = db.buscar_adjudicatarios(q, por_pagina, offset)
    return {
        **resultado,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, (resultado["total"] + por_pagina - 1) // por_pagina),
    }


@app.get("/adjudicatarios/{id}", tags=["Adjudicatarios"])
def perfil_adjudicatario(id: str):
    """
    Perfil completo de un adjudicatario: resumen agregado, distribución por tipo de contrato,
    evolución anual y top 20 organismos contratantes.

    El `id` es el `adjudicatario_id` que devuelven los listados (equivale al NIF normalizado).

    **Ejemplo:** `GET /adjudicatarios/B84498955`

    ```json
    {
      "adjudicatario_nombre": "FISHER SCIENTIFIC, S.L.",
      "adjudicatario_id": "B84498955",
      "adjudicatario_nif": "B84498955",
      "adjudicatario_pais": "ES",
      "num_contratos": 11863,
      "total_adjudicado": 30131053,
      "importe_medio": 2540,
      "primer_contrato": "2012-03-15",
      "ultimo_contrato": "2025-10-02",
      "por_tipo": [...],
      "por_anno": [...],
      "principales_organismos": [...]
    }
    ```
    """
    _verificar_datos()
    resultado = db.perfil_adjudicatario(id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Adjudicatario no encontrado")
    return resultado

