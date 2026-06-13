"""Pruebas unitarias para EliminarDuplicados."""
from etl.transformacion.eliminar_duplicados import EliminarDuplicados


def _reg(atom_id, organo, num_exp, fecha="2024-01-01", **extra):
    return {
        "id_atom": atom_id,
        "organo_nombre": organo,
        "num_expediente": num_exp,
        "fecha_actualizacion": fecha,
        **extra,
    }


def test_atom_duplicado_queda_mas_reciente():
    # T-01 — mismo atom:id en dos archivos distintos → se queda el de fecha más reciente
    ed = EliminarDuplicados()
    r1 = _reg("id:1", "Ayto Madrid", "EXP001", fecha="2024-01-01", importe=1000.0)
    r2 = _reg("id:1", "Ayto Madrid", "EXP001", fecha="2024-06-01", importe=1200.0)
    resultado = ed.eliminar_por_atom_id([r1, r2])
    assert len(resultado) == 1
    assert resultado[0]["fecha_actualizacion"] == "2024-06-01"
    assert resultado[0]["importe"] == 1200.0  # comprueba que no se queda el primero de la lista


def test_atom_sin_id_se_conserva():
    # T-02 — algunos feeds de menores no llevan atom:id, no hay que descartarlos
    ed = EliminarDuplicados()
    r = {"organo_nombre": "Ayto Madrid", "num_expediente": "EXP001"}
    resultado = ed.eliminar_por_atom_id([r])
    assert len(resultado) == 1


def test_exp_mismo_contrato_queda_mas_reciente():
    # T-03 — mismo expediente en dos descargas distintas: publicado en enero, adjudicado en junio
    ed = EliminarDuplicados()
    r1 = _reg("id:1", "Ayto Madrid", "EXP001", fecha="2024-01-01", estado="PUB")
    r2 = _reg("id:2", "Ayto Madrid", "EXP001", fecha="2024-06-01", estado="ADJ")
    resultado = ed.eliminar_por_expediente([r1, r2])
    assert len(resultado) == 1
    assert resultado[0]["estado"] == "ADJ"


def test_exp_sin_clave_se_conserva():
    # T-04 — sin organo_nombre o num_expediente no se puede construir la clave, pasa sin tocar
    ed = EliminarDuplicados()
    r = {"id_atom": "id:1", "fecha_actualizacion": "2024-01-01"}
    resultado = ed.eliminar_por_expediente([r])
    assert len(resultado) == 1


def test_exp_stats():
    # T-05 — los contadores tienen que reflejar cuántos registros se eliminaron en el paso 2
    ed = EliminarDuplicados()
    r1 = _reg("id:1", "Ayto Madrid", "EXP001", fecha="2024-01-01")
    r2 = _reg("id:2", "Ayto Madrid", "EXP001", fecha="2024-06-01")
    r3 = _reg("id:3", "Ayto Madrid", "EXP002")
    ed.eliminar_por_expediente([r1, r2, r3])
    s = ed.stats["expediente"]
    assert s["total_entrada"] == 3
    assert s["total_salida"] == 2
    assert s["registros_eliminados"] == 1
