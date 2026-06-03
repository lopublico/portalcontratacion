import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class EliminarDuplicados:
    """
    Quita duplicados de licitaciones que aparecen tanto en perfil como en agregacion.
    Clave de deduplicacion: (organo_id_plataforma, num_expediente).
    Si un registro no tiene los dos campos se conserva tal cual, no se fusiona.
    """

    def __init__(self):
        self._auditoria: List[Dict] = []
        self.stats: Dict[str, Any] = {}

    def eliminar(self, registros: List[Dict]) -> List[Dict]:
        self._auditoria = []
        self.stats = {
            'total_entrada': len(registros),
            'sin_clave_completa': 0,
            'grupos_sin_duplicado': 0,
            'grupos_fusionados': 0,
            'registros_eliminados_fusion': 0,
            'grupos_misma_fuente': 0,
            'registros_eliminados_misma_fuente': 0,
            'total_salida': 0,
        }

        if not registros:
            return []

        grupos = self._agrupar(registros)
        resultado = []

        for clave, grupo in grupos.items():
            registro_final, auditoria = self._resolver_grupo(clave, grupo)
            resultado.append(registro_final)
            if auditoria is not None:
                self._auditoria.append(auditoria)

        self.stats['total_salida'] = len(resultado)
        return resultado

    def guardar_auditoria(self, ruta: str) -> None:
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            for entrada in self._auditoria:
                f.write(json.dumps(entrada, ensure_ascii=False, default=str) + '\n')

    def obtener_estadisticas(self) -> Dict:
        return dict(self.stats)

    def imprimir_estadisticas(self) -> None:
        s = self.stats
        reduccion = s['registros_eliminados_fusion'] + s['registros_eliminados_misma_fuente']
        print(f"  entrada:  {s['total_entrada']:>10,}")
        print(f"  fusionados: {s['grupos_fusionados']:>8,}  (-{s['registros_eliminados_fusion']:,})")
        print(f"  dedup:    {s['grupos_misma_fuente']:>10,}  (-{s['registros_eliminados_misma_fuente']:,})")
        print(f"  salida:   {s['total_salida']:>10,}  (reduccion total: {reduccion:,})")

    def _agrupar(self, registros: List[Dict]) -> Dict[Tuple, List[Dict]]:
        grupos: Dict[Tuple, List[Dict]] = defaultdict(list)
        for i, registro in enumerate(registros):
            organo_id = registro.get('organo_id_plataforma')
            num_exp = registro.get('num_expediente')
            if organo_id and num_exp:
                clave: Tuple = ('exp', organo_id, num_exp)
            else:
                # sin clave completa nunca se fusiona con nadie
                clave = ('noclave', i)
                self.stats['sin_clave_completa'] += 1
            grupos[clave].append(registro)
        return grupos

    def _resolver_grupo(self, clave: Tuple, grupo: List[Dict]) -> Tuple[Dict, Optional[Dict]]:
        es_clave_completa = clave[0] == 'exp'
        organo_id = clave[1] if es_clave_completa else None
        num_exp = clave[2] if es_clave_completa else grupo[0].get('num_expediente')

        # caso simple: no hay duplicado
        if len(grupo) == 1:
            self.stats['grupos_sin_duplicado'] += 1
            return grupo[0], None

        por_fuente = self._agrupar_por_fuente(grupo)

        if len(por_fuente) == 1:
            # mismo expediente repetido en la misma fuente, nos quedamos con el mas reciente
            fuente = next(iter(por_fuente))
            registro_final = por_fuente[fuente]
            eliminados = len(grupo) - 1
            self.stats['grupos_misma_fuente'] += 1
            self.stats['registros_eliminados_misma_fuente'] += eliminados
            return registro_final, {
                'accion': 'misma_fuente',
                'organo_id_plataforma': organo_id,
                'num_expediente': num_exp,
                'registros_entrada': len(grupo),
                'registros_eliminados': eliminados,
                'fuente': fuente,
                'fecha_conservada': registro_final.get('fecha_actualizacion'),
            }

        # expediente en varias fuentes: fusionar campo a campo
        eliminados = len(grupo) - 1
        self.stats['grupos_fusionados'] += 1
        self.stats['registros_eliminados_fusion'] += eliminados
        registro_final, campos_conflictivos = self._fusionar(por_fuente)

        return registro_final, {
            'accion': 'fusionado',
            'organo_id_plataforma': organo_id,
            'num_expediente': num_exp,
            'registros_entrada': len(grupo),
            'registros_eliminados': eliminados,
            'fuentes': list(por_fuente.keys()),
            'campos_conflictivos': campos_conflictivos,
        }

    def _agrupar_por_fuente(self, grupo: List[Dict]) -> Dict[str, Dict]:
        """por cada fuente nos quedamos con el registro mas reciente"""
        por_fuente: Dict[str, Dict] = {}
        for reg in grupo:
            fuente = reg.get('_fuente') or 'unknown'
            if fuente not in por_fuente:
                por_fuente[fuente] = reg
            else:
                fecha_actual = por_fuente[fuente].get('fecha_actualizacion') or ''
                fecha_nueva = reg.get('fecha_actualizacion') or ''
                if fecha_nueva > fecha_actual:
                    por_fuente[fuente] = reg
        return por_fuente

    def _fusionar(self, por_fuente: Dict[str, Dict]) -> Tuple[Dict, Dict]:
        fuentes = list(por_fuente.keys())
        resultado = por_fuente[fuentes[0]].copy()
        campos_conflictivos: Dict[str, Dict] = {}
        for fuente_otro in fuentes[1:]:
            resultado, nuevos = self._fusionar_dos(resultado, por_fuente[fuente_otro], fuentes[0], fuente_otro)
            campos_conflictivos.update(nuevos)
        return resultado, campos_conflictivos

    def _fusionar_dos(self, base: Dict, otro: Dict, nombre_base: str, nombre_otro: str) -> Tuple[Dict, Dict]:
        resultado: Dict = {}
        conflictos: Dict[str, Dict] = {}
        todos_campos = set(base.keys()) | set(otro.keys())

        for campo in todos_campos:
            v_base = base.get(campo)
            v_otro = otro.get(campo)

            if v_base is None and v_otro is None:
                resultado[campo] = None
            elif v_base is None:
                resultado[campo] = v_otro
            elif v_otro is None:
                resultado[campo] = v_base
            elif v_base == v_otro:
                resultado[campo] = v_base
            elif campo == '_fuente':
                resultado[campo] = f"{nombre_base}+{nombre_otro}"
            elif isinstance(v_base, list) and isinstance(v_otro, list):
                # union sin duplicados, agregacion va primero (mas fiable)
                orden = v_otro + v_base if nombre_otro == 'agregacion' else v_base + v_otro
                vistos: set = set()
                union = []
                for item in orden:
                    k = str(item)
                    if k not in vistos:
                        vistos.add(k)
                        union.append(item)
                resultado[campo] = union
            else:
                # valor distinto en cada fuente: priorizamos agregacion
                if nombre_otro == 'agregacion':
                    elegido, valor = nombre_otro, v_otro
                elif nombre_base == 'agregacion':
                    elegido, valor = nombre_base, v_base
                else:
                    elegido, valor = nombre_otro, v_otro

                resultado[campo] = valor
                conflictos[campo] = {
                    nombre_base: v_base, nombre_otro: v_otro,
                    'elegido_de': elegido, 'valor_resultado': valor,
                }

        return resultado, conflictos
