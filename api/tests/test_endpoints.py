"""Pruebas de los endpoints de la API Lo Público."""
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_CONTRATOS = {
    "total": 1,
    "pagina": 1,
    "por_pagina": 20,
    "paginas": 1,
    "resultados": [{"tipo": "licitaciones", "num_expediente": "EXP001", "titulo": "Test"}],
}
_ESTADISTICAS = {"total": 100, "por_tipo": [], "pyme": {}, "top_organismos": [], "top_adjudicatarios": []}


def test_contratos_sin_parquet_devuelve_503():
    # T-11 — si el parquet no existe la API no puede responder, tiene que avisar con 503
    with patch("db.parquet_disponible", return_value=False):
        r = client.get("/contratos")
    assert r.status_code == 503


def test_contratos_tipo_invalido_devuelve_400():
    # T-12 — "invalido" no es licitaciones/menores/encargos/consultas
    with patch("db.parquet_disponible", return_value=True):
        r = client.get("/contratos?tipo=invalido")
    assert r.status_code == 400


def test_contratos_fecha_formato_incorrecto_devuelve_400():
    # T-13 — el endpoint espera YYYY-MM-DD, no DD-MM-YYYY
    with patch("db.parquet_disponible", return_value=True):
        r = client.get("/contratos?fecha_desde=15-01-2024")
    assert r.status_code == 400


def test_contratos_fechas_invertidas_devuelve_400():
    # T-14 — fecha_desde posterior a fecha_hasta no tiene sentido
    with patch("db.parquet_disponible", return_value=True):
        r = client.get("/contratos?fecha_desde=2024-12-01&fecha_hasta=2024-01-01")
    assert r.status_code == 400


def test_contratos_orden_invalido_devuelve_400():
    # T-15 — solo se admiten los campos de orden definidos en _ORDENES_VALIDOS
    with patch("db.parquet_disponible", return_value=True):
        r = client.get("/contratos?orden=precio_desc")
    assert r.status_code == 400


def test_contratos_ok_devuelve_200():
    # T-16 — petición válida con db mockeada, tiene que devolver 200
    with patch("db.parquet_disponible", return_value=True), \
         patch("db.listar_contratos", return_value=_CONTRATOS):
        r = client.get("/contratos")
    assert r.status_code == 200


def test_organismo_no_encontrado_devuelve_404():
    # T-17 — perfil_organismo devuelve None cuando el id no existe en el parquet
    with patch("db.parquet_disponible", return_value=True), \
         patch("db.perfil_organismo", return_value=None):
        r = client.get("/organismos/PL9999999")
    assert r.status_code == 404


def test_adjudicatario_no_encontrado_devuelve_404():
    # T-18 — igual que organismos pero para adjudicatarios
    with patch("db.parquet_disponible", return_value=True), \
         patch("db.perfil_adjudicatario", return_value=None):
        r = client.get("/adjudicatarios/B99999999")
    assert r.status_code == 404


def test_estadisticas_ok_devuelve_200():
    # T-19 — el endpoint de estadísticas devuelve 200 con datos mockeados
    with patch("db.parquet_disponible", return_value=True), \
         patch("db.estadisticas_generales", return_value=_ESTADISTICAS):
        r = client.get("/estadisticas")
    assert r.status_code == 200


def test_exportar_tipo_invalido_devuelve_400():
    # T-20 — formato=csv es obligatorio; sin él FastAPI devuelve 422 antes de llegar a la validación del tipo
    with patch("db.parquet_disponible", return_value=True):
        r = client.get("/contratos/exportar?formato=csv&tipo=tipoquenoexiste")
    assert r.status_code == 400
