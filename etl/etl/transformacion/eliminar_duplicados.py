from collections import defaultdict
from tqdm import tqdm
from typing import Any, Dict, List, Optional, Tuple


class EliminarDuplicados:
    """
    Dos pasos:
    - eliminar_por_atom_id: ZIPs solapados duplican el mismo atom:id. Se conserva el más reciente.
    - eliminar_por_expediente: actualizaciones de estado generan atom:ids distintos para el mismo expediente.
    """

    def __init__(self):
        self.stats: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Paso 1 — todos los tipos
    # ------------------------------------------------------------------

    def eliminar_por_atom_id(self, registros: List[Dict]) -> List[Dict]:
        if not registros:
            return []

        grupos: Dict[str, List[Dict]] = defaultdict(list)
        sin_id = []
        for r in tqdm(registros, desc='    agrupando atom:id', unit='reg', leave=False):
            atom_id = r.get('id_atom')
            if atom_id:
                grupos[atom_id].append(r)
            else:
                sin_id.append(r)

        resultado = []
        duplicados = 0
        for grupo in tqdm(grupos.values(), desc='    resolviendo atom:id', unit='grupo', leave=False):
            mejor = max(grupo, key=lambda r: r.get('fecha_actualizacion') or '')
            resultado.append(mejor)
            duplicados += len(grupo) - 1

        resultado.extend(sin_id)

        self.stats['atom_id'] = {
            'total_entrada': len(registros),
            'duplicados_eliminados': duplicados,
            'total_salida': len(resultado),
        }
        return resultado

    # ------------------------------------------------------------------
    # Paso 2 — solo licitaciones
    # ------------------------------------------------------------------

    def eliminar_por_expediente(self, registros: List[Dict]) -> List[Dict]:
        self.stats['expediente'] = {
            'total_entrada': len(registros),
            'sin_clave_completa': 0,
            'grupos_sin_duplicado': 0,
            'grupos_deduplicados': 0,
            'registros_eliminados': 0,
            'total_salida': 0,
        }

        if not registros:
            return []

        grupos = self._agrupar(registros)
        resultado = []

        for clave, grupo in tqdm(grupos.items(), total=len(grupos), desc='  deduplicando', unit='grupo', leave=False):
            registro_final = self._resolver_grupo(clave, grupo)
            resultado.append(registro_final)

        self.stats['expediente']['total_salida'] = len(resultado)
        return resultado

    def imprimir_estadisticas(self) -> None:
        if 'atom_id' in self.stats:
            s = self.stats['atom_id']
            print(f"  atom:id — entrada: {s['total_entrada']:,}  eliminados: {s['duplicados_eliminados']:,}  salida: {s['total_salida']:,}")
        if 'expediente' in self.stats:
            s = self.stats['expediente']
            print(f"  exp     — entrada: {s['total_entrada']:,}  eliminados: {s['registros_eliminados']:,}  salida: {s['total_salida']:,}")

    def _agrupar(self, registros: List[Dict]) -> Dict[Tuple, List[Dict]]:
        grupos: Dict[Tuple, List[Dict]] = defaultdict(list)
        for i, registro in enumerate(registros):
            organo = registro.get('organo_nombre')
            num_exp = registro.get('num_expediente')
            if organo and num_exp and len(num_exp.strip()) <= 50:
                clave: Tuple = ('exp', organo.strip(), num_exp.strip().upper())
            else:
                clave = ('noclave', i)
                self.stats['expediente']['sin_clave_completa'] += 1
            grupos[clave].append(registro)
        return grupos

    def _resolver_grupo(self, clave: Tuple, grupo: List[Dict]) -> Dict:
        if len(grupo) == 1:
            self.stats['expediente']['grupos_sin_duplicado'] += 1
            return grupo[0]

        mejor = max(grupo, key=lambda r: r.get('fecha_actualizacion') or '')
        eliminados = len(grupo) - 1

        self.stats['expediente']['grupos_deduplicados'] += 1
        self.stats['expediente']['registros_eliminados'] += eliminados

        return mejor
