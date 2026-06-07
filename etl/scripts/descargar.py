"""
Descarga datos de PLACSP y genera el parquet.

Uso:
    python scripts/descargar.py                   # todo historico + parquet
    python scripts/descargar.py --solo-descargar              # solo descarga
    python scripts/descargar.py l --a 2024 --solo-descargar  # solo descarga, año concreto
    python scripts/descargar.py --solo-procesar               # solo procesa lo descargado
    python scripts/descargar.py l                 # solo licitaciones (historico completo)
    python scripts/descargar.py l --a 2024        # licitaciones, año concreto
    python scripts/descargar.py l --a 2026 --m 3  # licitaciones, mes concreto
    python scripts/descargar.py cm --a 2026 --m 1
    python scripts/descargar.py e --a 2025
    python scripts/descargar.py cp --a 2025

Alias de tipo: l=licitaciones  cm=menores (contratos menores)  e=encargos  cp=consultas (consultas preliminares)
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tqdm import tqdm
from etl.extraccion.descargador import DescargadorPLACSP

AÑO_ACTUAL = datetime.now().year
MES_ACTUAL = datetime.now().month

ALIAS = {
    'l':  'licitaciones',
    'cm': 'menores',
    'e':  'encargos',
    'cp': 'consultas',
}


def descargar_todo(solo_tipo=None, solo_fuente=None, solo_anio=None, solo_mes=None):
    d = DescargadorPLACSP()
    fallos: dict = {}

    for tipo, config in DescargadorPLACSP.CONFIGURACION_TIPOS.items():
        if solo_tipo and tipo != solo_tipo:
            continue

        # cuantos archivos esperamos descargar, para inicializar la barra de progreso
        total = 0
        for fuente, cfg in config['fuentes'].items():
            if solo_fuente and fuente != solo_fuente:
                continue
            if solo_anio:
                total += 1 if solo_anio < AÑO_ACTUAL else (1 if solo_mes else MES_ACTUAL)
            else:
                total += AÑO_ACTUAL - cfg['desde']
                total += MES_ACTUAL if config['permite_mensual'] else 1

        ok = 0
        fallos_tipo = []

        t0_tipo = time.time()
        # pbar_bytes es una barra separada que solo muestra la velocidad de descarga agregada
        with tqdm(desc=f'  {tipo}', total=total, unit='archivo', leave=True) as pbar, \
             tqdm(unit='B', unit_scale=True, unit_divisor=1024, leave=False,
                  bar_format='  {rate_fmt}') as pbar_bytes:
            for fuente, cfg_fuente in config['fuentes'].items():
                if solo_fuente and fuente != solo_fuente:
                    continue

                if solo_anio and solo_anio < AÑO_ACTUAL:
                    años = [solo_anio]
                elif not solo_anio:
                    años = list(range(cfg_fuente['desde'], AÑO_ACTUAL))
                else:
                    años = []

                if años:
                    # cada año es un zip independiente, se descargan en paralelo
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        futuros = {
                            # silencioso=True para que los threads no mezclen sus prints
                            pool.submit(d.descargar_archivo, tipo, fuente, año, None, True, pbar_bytes): (fuente, año, None)
                            for año in años
                        }
                        for futuro in as_completed(futuros):
                            if futuro.result():
                                ok += 1
                            else:
                                fallos_tipo.append(futuros[futuro])
                            pbar.update(1)

                # el año en curso se publica por meses; los anteriores vienen en un zip anual
                descarga_mensual = (not solo_anio or solo_anio == AÑO_ACTUAL) and config['permite_mensual']
                if descarga_mensual:
                    meses = [solo_mes] if solo_mes else list(range(1, MES_ACTUAL + 1))
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        futuros_mes = {
                            pool.submit(d.descargar_archivo, tipo, fuente, AÑO_ACTUAL, mes, True, pbar_bytes): (fuente, AÑO_ACTUAL, mes)
                            for mes in meses
                        }
                        for futuro in as_completed(futuros_mes):
                            if futuro.result():
                                ok += 1
                            else:
                                fallos_tipo.append(futuros_mes[futuro])
                            pbar.update(1)
                elif not solo_anio or solo_anio == AÑO_ACTUAL:
                    resultado = d.descargar_archivo(tipo, fuente, AÑO_ACTUAL, mes=None, silencioso=True, pbar_bytes=pbar_bytes)
                    if resultado:
                        ok += 1
                    else:
                        fallos_tipo.append((fuente, AÑO_ACTUAL, None))
                    pbar.update(1)

        fallos[tipo] = fallos_tipo
        sufijo = f"  ({len(fallos_tipo)} sin datos en servidor)" if fallos_tipo else ""
        m, s = divmod(int(time.time() - t0_tipo), 60)
        t_str = f"{m}m {s}s" if m else f"{s}s"
        print(f"\n  {tipo:<25} {ok:>4} archivo(s)  {t_str}{sufijo}")

    return fallos


def reintentar_fallos(fallos: dict):
    d = DescargadorPLACSP()
    nuevos_fallos: dict = {}

    for tipo, lista in fallos.items():
        if not lista:
            nuevos_fallos[tipo] = []
            continue

        print(f"\n  {tipo} — reintentando {len(lista)} archivo(s)...")
        siguen_fallando = []
        for fuente, año, mes in lista:
            resultado = d.descargar_archivo(tipo, fuente, año, mes=mes, silencioso=False)
            if not resultado:
                siguen_fallando.append((fuente, año, mes))
        nuevos_fallos[tipo] = siguen_fallando

    return nuevos_fallos


def _mostrar_fallos(fallos: dict):
    total = sum(len(v) for v in fallos.values())
    if total == 0:
        return
    print(f"\n  {total} archivo(s) no descargados:")
    for tipo, lista in fallos.items():
        for fuente, año, mes in lista:
            periodo = f"{año}-{str(mes).zfill(2)}" if mes else str(año)
            print(f"    {tipo}/{fuente}/{periodo}")


def _hay_fallos(fallos: dict) -> bool:
    return any(fallos.values())


def _borrar_cache_procesado():
    # si hay datos nuevos el procesado anterior ya no es valido
    dir_salida = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'processed')
    for tipo in DescargadorPLACSP.CONFIGURACION_TIPOS:
        ruta_done = os.path.join(dir_salida, f'{tipo}.done')
        if os.path.exists(ruta_done):
            os.remove(ruta_done)


def procesar():
    import subprocess
    result = subprocess.run(
        [sys.executable, 'scripts/procesar.py', '--parquet'],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return result.returncode == 0


def _ya_corriendo():
    import subprocess
    pid_actual = str(os.getpid())
    result = subprocess.run(['pgrep', '-f', 'scripts/descargar.py|scripts/procesar.py'], text=True, capture_output=True)
    pids = [p for p in result.stdout.strip().splitlines() if p != pid_actual]
    return pids[0] if pids else None


def main():
    pid = _ya_corriendo()
    if pid:
        print(f"Instancia anterior del ETL (PID {pid}) encontrada, terminándola...")
        os.kill(int(pid), 15)  # SIGTERM, no SIGKILL, para que pueda limpiar los .tmp abiertos

    parser = argparse.ArgumentParser()
    parser.add_argument('tipo', nargs='?', default=None, help='l|cm|e|cp o nombre completo')
    parser.add_argument('--solo-descargar', action='store_true')
    parser.add_argument('--solo-procesar',  action='store_true')
    parser.add_argument('--fuente', default=None, help='perfil|agregacion')
    parser.add_argument('--a', type=int, dest='anio', default=None)
    parser.add_argument('--m', type=int, dest='mes',  default=None)
    args = parser.parse_args()

    tipo = ALIAS.get(args.tipo, args.tipo) if args.tipo else None
    if tipo and tipo not in DescargadorPLACSP.CONFIGURACION_TIPOS:
        parser.error(f"tipo '{args.tipo}' no reconocido. Usa: {', '.join(ALIAS)}")

    solo_descargar = args.solo_descargar
    solo_procesar  = args.solo_procesar

    if not solo_procesar:
        partes = [x for x in [tipo, args.fuente, str(args.anio) if args.anio else None, str(args.mes) if args.mes else None] if x]
        filtro = f" [{'/'.join(partes)}]" if partes else ""
        print(f"Descargando{filtro}...")
        _borrar_cache_procesado()
        fallos = descargar_todo(
            solo_tipo=tipo,
            solo_fuente=args.fuente,
            solo_anio=args.anio,
            solo_mes=args.mes,
        )

        while _hay_fallos(fallos):
            _mostrar_fallos(fallos)
            try:
                resp = input("\n¿Reintentar archivos fallidos? [s/n]: ").strip().lower()
            except EOFError:
                break
            if resp != 's':
                break
            fallos = reintentar_fallos(fallos)

        if _hay_fallos(fallos):
            _mostrar_fallos(fallos)
            print("\nSe continuará con los archivos disponibles.")

        print("\nDescarga completada.")

    if not solo_descargar:
        print("\nProcesando y generando parquet...")
        ok = procesar()
        if ok:
            print("\nParquet generado en data/processed/contratos.parquet")
        else:
            print("\nError al procesar. Revisa la salida.")
            sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrumpido.')
        sys.exit(0)
