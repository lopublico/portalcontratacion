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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
        print("ejecuta: python ../etl/scripts/procesar_todo.py --parquet")
    yield


app = FastAPI(
    title="Portal de Contratacion Publica",
    description="Datos extraidos de PLACSP. Solo lectura.",
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
DIR_DATOS = Path(db.PARQUET).parent


def _verificar_datos():
    if not db.parquet_disponible():
        raise HTTPException(status_code=503, detail="Datos no disponibles. Ejecuta procesar_todo.py --parquet")


def _validar_tipo(tipo: Optional[str]):
    if tipo and tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo no valido. Usa: {', '.join(sorted(TIPOS_VALIDOS))}")


# --- info ---

@app.get("/", tags=["Info"])
def raiz():
    return {
        "api": "Portal de Contratacion Publica",
        "version": "0.1.0",
        "datos_disponibles": db.parquet_disponible(),
        "tipos": sorted(TIPOS_VALIDOS),
        "docs": "/docs",
    }


# --- estadisticas ---

@app.get("/estadisticas", tags=["Estadísticas"])
def estadisticas(tipo: Optional[str] = Query(None)):
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_generales(tipo)


@app.get("/estadisticas/anual", tags=["Estadísticas"])
def estadisticas_anual(tipo: Optional[str] = Query(None)):
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_por_anno(tipo)


@app.get("/estadisticas/mensual", tags=["Estadísticas"])
def estadisticas_mensual(
    tipo: Optional[str] = Query(None),
    anno: int = Query(default_factory=lambda: datetime.now().year),
):
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_por_mes(tipo, anno)


@app.get("/estadisticas/cpv", tags=["Estadísticas"])
def estadisticas_cpv(
    tipo: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
    _verificar_datos()
    _validar_tipo(tipo)
    return db.estadisticas_cpv(tipo, limit)


# --- contratos ---

@app.get("/contratos", tags=["Contratos"])
def listar_contratos(
    tipo: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="busqueda en titulo y objeto"),
    organismo_nif: Optional[str] = Query(None),
    organismo_id: Optional[str] = Query(None),
    adjudicatario_nif: Optional[str] = Query(None),
    adjudicatario_q: Optional[str] = Query(None),
    tipo_contrato: Optional[str] = Query(None, description="1 Obras · 2 Servicios · 3 Suministros..."),
    anno: Optional[int] = Query(None),
    cpv: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="PUB · EV · ADJ · RES · ANUL · DES"),
    pyme: Optional[bool] = Query(None),
    importe_min: Optional[float] = Query(None, ge=0),
    importe_max: Optional[float] = Query(None, ge=0),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    tipo_procedimiento: Optional[str] = Query(None),
    orden: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    _verificar_datos()
    _validar_tipo(tipo)

    if estado and estado not in ESTADOS_VALIDOS:
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


@app.get("/contratos/{num_expediente}", tags=["Contratos"])
def obtener_contrato(num_expediente: str):
    _verificar_datos()
    resultados = db.obtener_contrato(num_expediente)
    if not resultados:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return resultados


# --- organismos ---

@app.get("/organismos", tags=["Organismos"])
def listar_organismos(
    q: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
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
    _verificar_datos()
    resultado = db.perfil_organismo(id_plataforma)
    if not resultado:
        raise HTTPException(status_code=404, detail="Organismo no encontrado")
    return resultado


# --- adjudicatarios ---

@app.get("/adjudicatarios", tags=["Adjudicatarios"])
def listar_adjudicatarios(
    q: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
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
    _verificar_datos()
    resultado = db.perfil_adjudicatario(id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Adjudicatario no encontrado")
    return resultado


# --- descargas ---

@app.get("/descargas", tags=["Descargas"])
def listar_descargas():
    """lista los jsonl disponibles con su tamaño"""
    _verificar_datos()
    tipos_disponibles = []
    for tipo in sorted(TIPOS_VALIDOS):
        ruta = DIR_DATOS / f"{tipo}.jsonl"
        if ruta.exists():
            tipos_disponibles.append({
                "tipo": tipo,
                "fichero": f"{tipo}.jsonl",
                "tamaño_mb": round(ruta.stat().st_size / 1024 / 1024, 1),
            })
    return {"ficheros": tipos_disponibles}


@app.get("/descargas/{tipo}", tags=["Descargas"])
def descargar_tipo(tipo: str):
    _verificar_datos()
    _validar_tipo(tipo)
    ruta = DIR_DATOS / f"{tipo}.jsonl"
    if not ruta.exists():
        raise HTTPException(status_code=503, detail=f"{tipo}.jsonl no encontrado")
    return FileResponse(path=ruta, media_type="application/x-ndjson", filename=f"{tipo}.jsonl")
