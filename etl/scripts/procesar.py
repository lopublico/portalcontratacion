"""
Procesa todos los tipos y exporta los datos.

Uso:
    python scripts/procesar.py
    python scripts/procesar.py --parquet
    python scripts/procesar.py --sin-deduplicar --parquet
"""

import argparse
import csv
import json
import os
import sys
import time
DIR_ETL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_ETL)

from glob import glob
from tqdm import tqdm

from etl.transformacion.parser_atom import ParserATOM
from etl.transformacion.eliminar_duplicados import EliminarDuplicados


DIR_SALIDA = os.path.join(DIR_ETL, 'data', 'processed')

TIPOS = [
    'licitaciones',
    'menores',
    'encargos',
    'consultas',
]


def _parsear(tipo: str) -> tuple:
    archivos = glob(os.path.join(DIR_ETL, 'data', 'raw', tipo, '**', '*.atom'), recursive=True)
    if not archivos:
        return [], 0, 0.0

    parser = ParserATOM(tipo=tipo)
    registros = []
    errores = 0

    t0 = time.time()
    for archivo in tqdm(archivos, desc=f'  {tipo}', unit='archivo', leave=False):
        try:
            registros.extend(parser.parsear_archivo(archivo))
        except Exception:
            errores += 1

    return registros, errores, time.time() - t0


def _exportar_jsonl(registros: list, ruta: str) -> None:
    # calculamos antes todas las claves para que cada linea tenga los mismos campos aunque falten datos
    # asi DuckDB puede inferir el schema completo desde la primera pasada sin leer todo el fichero
    todas_claves = []
    for r in registros:
        for k in r.keys():
            if k not in todas_claves:
                todas_claves.append(k)
    with open(ruta, 'w', encoding='utf-8') as f:
        for r in registros:
            row = {k: r.get(k) for k in todas_claves}
            f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')


def _exportar_csv(registros: list, ruta: str) -> None:
    if not registros:
        open(ruta, 'w').close()
        return

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


def _fmt_tiempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def _sql_sin_json(con, ruta_jsonl: str) -> str:
    # DuckDB a veces infiere la misma columna como JSON en un tipo y como VARCHAR en otro
    # al hacer el UNION eso rompe con error de tipo, casteamos a VARCHAR las que detectamos como JSON
    base = f"read_json_auto('{ruta_jsonl}', maximum_object_size=100000000, ignore_errors=true, sample_size=500)"
    schema = con.execute(f"DESCRIBE SELECT * FROM {base}").fetchall()
    base_full = f"read_json_auto('{ruta_jsonl}', maximum_object_size=100000000, ignore_errors=true)"
    json_cols = [row[0] for row in schema if 'JSON' in str(row[1]).upper()]
    if not json_cols:
        return f"SELECT * FROM {base_full}"
    casts = ', '.join(f'"{c}"::VARCHAR AS "{c}"' for c in json_cols)
    otros = ', '.join(f'"{row[0]}"' for row in schema if row[0] not in json_cols)
    select = f"{otros}, {casts}" if otros else casts
    return f"SELECT {select} FROM {base_full}"


def _generar_parquet(tipos_con_datos: list, dir_salida: str) -> float:
    import duckdb

    t0 = time.time()
    con = duckdb.connect()
    # el parquet combinado puede superar la RAM disponible, temp_directory evita quedarse sin memoria
    con.execute("SET memory_limit='4GB'")
    con.execute("SET temp_directory='/tmp'")
    parquets_tipo = []

    for tipo in tipos_con_datos:
        ruta_jsonl = os.path.join(dir_salida, f'{tipo}.jsonl')
        ruta_pq = os.path.join(dir_salida, f'{tipo}.parquet')
        if not os.path.exists(ruta_jsonl) or os.path.getsize(ruta_jsonl) == 0:
            continue
        try:
            sql = _sql_sin_json(con, ruta_jsonl)
            con.execute(f"COPY ({sql}) TO '{ruta_pq}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            mb = os.path.getsize(ruta_pq) / 1024 / 1024
            print(f"  {tipo}.parquet  {mb:>8.1f} MB")
            parquets_tipo.append(ruta_pq)
        except Exception as e:
            print(f"  Advertencia: {tipo} omitido ({e})")

    if not parquets_tipo:
        con.close()
        return time.time() - t0

    ruta = os.path.join(dir_salida, 'contratos.parquet')
    lista = ', '.join(f"'{p}'" for p in parquets_tipo)
    # cada tipo tiene columnas distintas, union_by_name rellena con NULL las que faltan en cada uno
    con.execute(f"COPY (SELECT * FROM read_parquet([{lista}], union_by_name=true)) TO '{ruta}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    mb = os.path.getsize(ruta) / 1024 / 1024
    print(f"  contratos.parquet  {mb:>8.1f} MB")
    return time.time() - t0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sin-deduplicar', action='store_true')
    parser.add_argument('--parquet', action='store_true')
    parser.add_argument('--forzar', action='store_true', help='Reprocesa todos los tipos aunque ya estén cacheados')
    args = parser.parse_args()

    os.makedirs(DIR_SALIDA, exist_ok=True)

    if args.forzar:
        for tipo in TIPOS:
            for ext in ('done', 'jsonl', 'csv', 'parquet'):
                ruta = os.path.join(DIR_SALIDA, f'{tipo}.{ext}')
                if os.path.exists(ruta):
                    os.remove(ruta)
        ruta_combinado = os.path.join(DIR_SALIDA, 'contratos.parquet')
        if os.path.exists(ruta_combinado):
            os.remove(ruta_combinado)

    tipos_procesados = []
    conteos: dict = {}
    tiempos: dict = {}

    for tipo in TIPOS:
        ruta_done = os.path.join(DIR_SALIDA, f'{tipo}.done')
        ruta_jsonl = os.path.join(DIR_SALIDA, f'{tipo}.jsonl')

        # si .done existe el tipo ya fue procesado en una ejecucion anterior, lo saltamos
        if os.path.exists(ruta_done) and os.path.exists(ruta_jsonl):
            n = int(open(ruta_done).read().strip())
            mb = os.path.getsize(ruta_jsonl) / 1024 / 1024
            print(f"  {tipo:<30} {n:>10,}  (ya procesado, saltando)")
            print(f"  {tipo+'.jsonl':<35} {n:>10,}  {mb:>7.1f} MB")
            tipos_procesados.append(tipo)
            conteos[tipo] = n
            continue

        registros, errores, t_parseo = _parsear(tipo)
        n_entrada = len(registros)
        t_dedup = 0.0

        if not registros:
            print(f"  {tipo:<30} sin datos")
            continue

        tiempos[tipo] = {'parseo': t_parseo}

        if not args.sin_deduplicar:
            t0 = time.time()
            elim = EliminarDuplicados()

            # primer paso para todos los tipos: feeds solapados pueden traer el mismo atom:id duplicado
            registros = elim.eliminar_por_atom_id(registros)
            n_tras_atom = len(registros)

            # segundo paso solo para licitaciones: el mismo expediente aparece varias veces segun su estado
            if tipo == 'licitaciones':
                registros = elim.eliminar_por_expediente(registros)

            t_dedup = time.time() - t0
            tiempos[tipo]['dedup'] = t_dedup
            if tipo == 'licitaciones':
                print(f"  {tipo:<30} {n_entrada:>10,} -> {n_tras_atom:>10,} (atom:id)  -> {len(registros):>10,} (expediente)")
            else:
                print(f"  {tipo:<30} {n_entrada:>10,} -> {len(registros):>10,}  (-{n_entrada - len(registros):,} dedup)")
        else:
            sufijo = f"  ({errores} errores)" if errores else ""
            print(f"  {tipo:<30} {n_entrada:>10,}{sufijo}")

        for r in registros:
            r['tipo'] = tipo

        ruta_csv = os.path.join(DIR_SALIDA, f'{tipo}.csv')

        _exportar_jsonl(registros, ruta_jsonl)
        _exportar_csv(registros, ruta_csv)

        mb_jsonl = os.path.getsize(ruta_jsonl) / 1024 / 1024
        print(f"  {tipo+'.jsonl':<35} {len(registros):>10,}  {mb_jsonl:>7.1f} MB")

        open(ruta_done, 'w').write(str(len(registros)))

        tipos_procesados.append(tipo)
        conteos[tipo] = len(registros)
        del registros  # los datasets son grandes, soltamos memoria antes de pasar al siguiente tipo

    if not tipos_procesados:
        print("Sin datos. Ejecuta primero la descarga.")
        sys.exit(1)

    print()

    if args.parquet:
        print("  Generando parquet (puede tardar varios minutos)...")
        t_parquet = _generar_parquet(tipos_procesados, DIR_SALIDA)
    else:
        t_parquet = None

    print(f"\n  Total: {sum(conteos.values()):,} registros")

    if tiempos:
        print("\n  Tiempos:")
        for tipo, t in tiempos.items():
            parseo = _fmt_tiempo(t['parseo'])
            dedup = f"  dedup {_fmt_tiempo(t['dedup'])}" if 'dedup' in t else ""
            print(f"    {tipo:<20} parseo {parseo}{dedup}")
        if t_parquet is not None:
            print(f"    {'parquet':<20} {_fmt_tiempo(t_parquet)}")



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrumpido.')
        sys.exit(0)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
