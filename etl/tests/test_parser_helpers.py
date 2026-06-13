"""Pruebas unitarias para los métodos auxiliares de ParserATOM."""
import pytest
from etl.transformacion.parser_atom import ParserATOM


@pytest.fixture
def parser():
    return ParserATOM()


def test_parse_fecha_none(parser):
    # T-06 — campos de fecha opcionales vienen como None desde el XML, no debe explotar
    assert parser._parse_fecha(None) is None


def test_parse_fecha_iso_con_z(parser):
    # T-07 — PLACSP usa ISO 8601 con Z al final, hay que normalizarlo a YYYY-MM-DD HH:MM:SS
    assert parser._parse_fecha("2024-01-15T10:30:00Z") == "2024-01-15 10:30:00"


def test_parse_bool_true(parser):
    # T-08 — el XML trae "true"/"false" como texto, no booleanos Python
    assert parser._parse_bool("true") is True


def test_parse_bool_false(parser):
    # T-09
    assert parser._parse_bool("false") is False


def test_parsear_archivo_no_existente_lanza_error(parser):
    # T-10 — si la ruta no existe tiene que lanzar FileNotFoundError, no silenciar el fallo
    with pytest.raises(FileNotFoundError):
        parser.parsear_archivo("/ruta/que/no/existe.atom")
