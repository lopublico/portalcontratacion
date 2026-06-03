"""
descarga datos de PLACSP para un periodo dado

uso:
    python scripts/descargar.py --a 2026 --m 1          # todos los tipos, enero 2026
    python scripts/descargar.py licitaciones --a 2026 --m 1
    python scripts/descargar.py encargos --a 2025        # anual
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.extraccion.descargador import DescargadorPLACSP

ALIAS = {
    'l':  'licitaciones',
    'cm': 'menores',
    'e':  'encargos',
    'cp': 'consultas',
}
SOLO_ANUAL = {'encargos', 'consultas'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tipo', nargs='?', choices=ALIAS.keys(),
                        help='l, cm, e, cp (omitir para descargar todos)')
    parser.add_argument('--a', type=int, required=True, dest='anio', help='año')
    parser.add_argument('--m', type=int, dest='mes', help='mes (solo l y cm)')
    args = parser.parse_args()

    tipos = [ALIAS[args.tipo]] if args.tipo else list(ALIAS.values())
    d = DescargadorPLACSP()

    for tipo in tipos:
        config = DescargadorPLACSP.CONFIGURACION_TIPOS[tipo]
        mes = args.mes if config['permite_mensual'] else None
        if args.mes and tipo in SOLO_ANUAL:
            print(f"  {tipo}: no admite descarga mensual, descargando año completo")
        for fuente in config['fuentes']:
            d.descargar_archivo(tipo, fuente, args.anio, mes)


if __name__ == '__main__':
    main()
