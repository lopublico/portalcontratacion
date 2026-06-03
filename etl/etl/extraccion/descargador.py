import os
import requests
from typing import List, Dict, Optional
from datetime import datetime
import zipfile
from tqdm import tqdm


class DescargadorPLACSP:
    # nombres para mostrar en consola
    NOMBRES_TIPO = {
        'licitaciones': 'Licitaciones',
        'menores': 'Contratos Menores',
        'encargos': 'Encargos a Medios Propios',
        'consultas': 'Consultas Preliminares de Mercado',
    }

    # configuracion de cada tipo: fuentes, codigo de sindicacion, patron del zip
    # licitaciones tiene dos fuentes (perfil + agregacion) porque PLACSP las publica por duplicado
    CONFIGURACION_TIPOS = {
        'licitaciones': {
            'fuentes': {
                'perfil': {
                    'codigo': '643',
                    'archivo_patron': 'licitacionesPerfilesContratanteCompleto3_{periodo}.zip',
                    'desde': 2012
                },
                'agregacion': {
                    'codigo': '1044',
                    'archivo_patron': 'PlataformasAgregadasSinMenores_{periodo}.zip',
                    'desde': 2016
                }
            },
            'permite_mensual': True
        },
        'menores': {
            'fuentes': {
                'perfil': {
                    'codigo': '1143',
                    'archivo_patron': 'contratosMenoresPerfilesContratantes_{periodo}.zip',
                    'desde': 2018
                }
            },
            'permite_mensual': True
        },
        'encargos': {
            'fuentes': {
                'perfil': {
                    'codigo': '1383',
                    'archivo_patron': 'EMP_SectorPublico_{periodo}.zip',
                    'desde': 2021
                }
            },
            'permite_mensual': False
        },
        'consultas': {
            'fuentes': {
                'perfil': {
                    'codigo': '1403',
                    'archivo_patron': 'CPM_SectorPublico_{periodo}.zip',
                    'desde': 2022
                }
            },
            'permite_mensual': False
        },
    }

    BASE_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion"

    def __init__(self, directorio_descarga: str = "data/raw"):
        self.directorio_descarga = directorio_descarga
        os.makedirs(directorio_descarga, exist_ok=True)
        self.session = requests.Session()
        # user agent para que no lo bloquee el servidor
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; LoPublico/1.0)'
        })

    def descargar_archivo(self, tipo: str, fuente: str, anio: int, mes: Optional[int] = None) -> Optional[str]:
        """descarga un zip de PLACSP para el tipo/fuente/periodo dado"""
        if tipo not in self.CONFIGURACION_TIPOS:
            print(f"tipo '{tipo}' no valido")
            return None

        config_tipo = self.CONFIGURACION_TIPOS[tipo]

        if fuente not in config_tipo['fuentes']:
            print(f"fuente '{fuente}' no disponible para {tipo}")
            return None

        config_fuente = config_tipo['fuentes'][fuente]

        if anio < config_fuente['desde']:
            print(f"  {tipo} ({fuente}) solo disponible desde {config_fuente['desde']}")
            return None

        anio_actual = datetime.now().year

        # año actual se descarga por meses, el resto por año completo
        if mes and config_tipo['permite_mensual'] and anio == anio_actual:
            periodo = f"{anio}{str(mes).zfill(2)}"
            periodo_legible = f"{anio}-{str(mes).zfill(2)}"
        else:
            periodo = str(anio)
            periodo_legible = str(anio)

        nombre_archivo = config_fuente['archivo_patron'].format(periodo=periodo)
        url = f"{self.BASE_URL}/sindicacion_{config_fuente['codigo']}/{nombre_archivo}"

        directorio = os.path.join(self.directorio_descarga, tipo, 'historico', periodo_legible, fuente)
        os.makedirs(directorio, exist_ok=True)
        archivo_destino = os.path.join(directorio, nombre_archivo)

        # si ya esta descargado lo saltamos
        if os.path.exists(archivo_destino):
            print(f"  ya existe: {nombre_archivo}")
            if zipfile.is_zipfile(archivo_destino):
                self._extraer_zip(archivo_destino, directorio)
            return archivo_destino

        try:
            print(f"  descargando {periodo_legible} ({fuente})...")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(archivo_destino, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True, desc=f"  {periodo_legible}"
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            # comprobamos que es un zip valido (a veces PLACSP devuelve una pagina de error)
            if not zipfile.is_zipfile(archivo_destino):
                file_size = os.path.getsize(archivo_destino)
                if file_size < 1000:
                    print(f"  archivo invalido ({file_size} bytes), probablemente no disponible aun")
                    os.remove(archivo_destino)
                    return None

            self._extraer_zip(archivo_destino, directorio)
            return archivo_destino

        except requests.exceptions.RequestException as e:
            print(f"  error descargando: {e}")
            return None

    def _extraer_zip(self, archivo_zip: str, directorio_destino: str) -> bool:
        try:
            with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
                zip_ref.extractall(directorio_destino)
            return True
        except Exception as e:
            print(f"  error extrayendo zip: {e}")
            return False

    def descargar_tipo_completo(self, tipo: str, anio_inicio: int, anio_fin: Optional[int] = None) -> Dict[str, List[str]]:
        """descarga todos los archivos de un tipo para un rango de anios"""
        anio_fin = anio_fin or datetime.now().year
        anio_actual = datetime.now().year
        mes_actual = datetime.now().month
        resultados = {}

        print(f"\n{'='*60}")
        print(f"descargando {self.NOMBRES_TIPO[tipo]} ({anio_inicio}-{anio_fin})")
        print(f"{'='*60}")

        config = self.CONFIGURACION_TIPOS[tipo]

        for nombre_fuente, config_fuente in config['fuentes'].items():
            print(f"\nfuente: {nombre_fuente}")
            archivos_fuente = []
            anio_inicio_efectivo = max(anio_inicio, config_fuente['desde'])

            for anio in range(anio_inicio_efectivo, anio_fin + 1):
                if anio == anio_actual and config['permite_mensual']:
                    # los ultimos 2 meses suelen no estar consolidados
                    mes_limite = max(1, mes_actual - 2)
                    for mes in range(1, mes_limite + 1):
                        archivo = self.descargar_archivo(tipo, nombre_fuente, anio, mes)
                        if archivo:
                            archivos_fuente.append(archivo)
                else:
                    archivo = self.descargar_archivo(tipo, nombre_fuente, anio, None)
                    if archivo:
                        archivos_fuente.append(archivo)

            resultados[nombre_fuente] = archivos_fuente
            print(f"  {nombre_fuente}: {len(archivos_fuente)} archivo(s)")

        print(f"\ntotal: {sum(len(a) for a in resultados.values())} archivo(s)")
        return resultados

    def descargar_multiples_tipos(self, year: int, mes: Optional[int], tipos: List[str]) -> Dict[str, Dict[str, List[str]]]:
        resultados = {}
        periodo_str = f"{year}-{mes:02d}" if mes else str(year)
        print(f"\ndescargando {periodo_str}")

        for i, tipo in enumerate(tipos, 1):
            print(f"\n[{i}/{len(tipos)}] {self.NOMBRES_TIPO.get(tipo, tipo)}")
            config = self.CONFIGURACION_TIPOS[tipo]
            resultados_tipo = {}
            for fuente in config['fuentes'].keys():
                archivo = self.descargar_archivo(tipo, fuente, year, mes)
                resultados_tipo[fuente] = [archivo] if archivo else []
            resultados[tipo] = resultados_tipo

        total = sum(len(a) for t in resultados.values() for a in t.values())
        print(f"\ntotal: {total} archivo(s)")
        return resultados

    def descargar_rango_anos(self, year_inicio: int, year_fin: int, tipos: List[str]) -> Dict:
        """descarga un rango de anios completo para varios tipos"""
        resultados = {}
        year_actual = datetime.now().year

        print(f"\ndescargando {year_inicio}-{year_fin}")

        for year in range(year_inicio, year_fin + 1):
            print(f"\n--- {year} ---")
            if year == year_actual:
                mes_actual = datetime.now().month
                mes_limite = max(1, mes_actual - 2)
                resultados_año: Dict = {}
                for mes in range(1, mes_limite + 1):
                    for tipo, fuentes in self.descargar_multiples_tipos(year, mes, tipos).items():
                        if tipo not in resultados_año:
                            resultados_año[tipo] = {}
                        for fuente, archivos in fuentes.items():
                            resultados_año[tipo].setdefault(fuente, []).extend(archivos)
                resultados[year] = resultados_año
            else:
                resultados[year] = self.descargar_multiples_tipos(year, None, tipos)

        return resultados
