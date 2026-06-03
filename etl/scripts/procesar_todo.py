"""
Procesa los datos descargados y los exporta.

Genera JSONL y CSV por tipo, y opcionalmente un parquet con todo junto
(el parquet lo necesita la API).

Uso:
    python scripts/procesar_todo.py
    python scripts/procesar_todo.py --parquet
    python scripts/procesar_todo.py --sin-deduplicar --parquet
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glob import glob
from tqdm import tqdm
from etl.transformacion.parser_atom import ParserATOM
from etl.transformacion.eliminar_duplicados import EliminarDuplicados


DIR_SALIDA = 'data/processed'

# tipos en el orden en que se procesan
TIPOS = [
    'licitaciones',
    'menores',
    'encargos',
    'consultas',
]


def _parsear(tipo: str) -> tuple:
    """recorre todos los .atom de un tipo y devuelve (registros, errores)"""
    archivos = glob(f'data/raw/{tipo}/**/*.atom', recursive=True)
    if not archivos:
        return [], 0

    parser = ParserATOM(tipo=tipo)
    registros = []
    errores = 0

    for archivo in tqdm(archivos, desc=f'  {tipo}', unit='archivo', leave=False):
        try:
            registros.extend(parser.parsear_archivo(archivo))
        except Exception:
            errores += 1

    return registros, errores


def _exportar_jsonl(registros: list, ruta: str) -> None:
    with open(ruta, 'w', encoding='utf-8') as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')


def _exportar_csv(registros: list, ruta: str) -> None:
    if not registros:
        open(ruta, 'w').close()
        return

    # recopilar todas las columnas en orden de primera aparicion
    campos: list = []
    vistos: set = set()
    for r in registros:
        for k in r:
            if k not in vistos:
                vistos.add(k)
                campos.append(k)

    with open(ruta, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        for r in registros:
            w.writerow({
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                for k, v in r.items()
            })


def _generar_parquet(todos: list, dir_salida: str) -> None:
    """genera el parquet que usa la API — requiere duckdb"""
    import duckdb

    # volcamos a json temporal y duckdb lo lee
    tmp = os.path.join(dir_salida, '_tmp.json')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(todos, f, ensure_ascii=False)

    try:
        ruta = os.path.join(dir_salida, 'contratos.parquet')
        con = duckdb.connect()
        con.sql(f"""
            COPY (
                SELECT * FROM read_json_auto('{tmp}', maximum_object_size=100000000, ignore_errors=true)
            )
            TO '{ruta}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        con.close()
        mb = os.path.getsize(ruta) / 1024 / 1024
        print(f"  contratos.parquet  {mb:.1f} MB")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sin-deduplicar', action='store_true',
                        help='no deduplica licitaciones')
    parser.add_argument('--parquet', action='store_true',
                        help='genera contratos.parquet para la API')
    args = parser.parse_args()

    os.makedirs(DIR_SALIDA, exist_ok=True)

    todos = []
    conteos: dict = {}

    for tipo in TIPOS:
        registros, errores = _parsear(tipo)

        if not registros:
            print(f"  {tipo:<30} sin datos")
            continue

        n_entrada = len(registros)

        if tipo == 'licitaciones' and not args.sin_deduplicar:
            eliminador = EliminarDuplicados()
            registros = eliminador.eliminar(registros)
            stats = eliminador.obtener_estadisticas()
            reduccion = stats['registros_eliminados_fusion'] + stats['registros_eliminados_misma_fuente']
            ruta_auditoria = os.path.join(DIR_SALIDA, 'auditoria_deduplicacion.jsonl')
            eliminador.guardar_auditoria(ruta_auditoria)
            print(f"  {tipo:<30} {n_entrada:>10,} -> {len(registros):>10,}  (-{reduccion:,} dedup)")
        else:
            sufijo = f"  ({errores} errores)" if errores else ""
            print(f"  {tipo:<30} {n_entrada:>10,}{sufijo}")

        # añadir campo tipo a cada registro (necesario para filtrar en la API)
        for r in registros:
            r['tipo'] = tipo

        todos.extend(registros)
        conteos[tipo] = len(registros)

    if not todos:
        print("sin datos, ejecuta primero la descarga")
        sys.exit(1)

    print()
    for tipo in TIPOS:
        registros_tipo = [r for r in todos if r.get('tipo') == tipo]
        if not registros_tipo:
            continue

        ruta_jsonl = os.path.join(DIR_SALIDA, f'{tipo}.jsonl')
        ruta_csv = os.path.join(DIR_SALIDA, f'{tipo}.csv')
        _exportar_jsonl(registros_tipo, ruta_jsonl)
        _exportar_csv(registros_tipo, ruta_csv)

        mb = os.path.getsize(ruta_jsonl) / 1024 / 1024
        print(f"  {tipo+'.jsonl':<35} {conteos[tipo]:>10,}  {mb:.1f} MB")

    if args.parquet:
        _generar_parquet(todos, DIR_SALIDA)

    print(f"\n  total: {sum(conteos.values()):,} registros")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\ninterrumpido')
        sys.exit(0)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
