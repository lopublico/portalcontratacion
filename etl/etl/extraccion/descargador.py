import os
import time
import requests
import urllib3
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import zipfile
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
    # con format se puede reemplazar {periodo} por el año o año+mes segun corresponda
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
                    'desde': 2022  # antes 2021 en el repo, pero PLACSP no publica ese año
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

    def __init__(self, directorio_descarga: str = str(Path(__file__).parent.parent.parent / 'data' / 'raw')):  # antes era "data/raw" relativa, que se rompe si no se ejecuta desde el directorio del ETL
        self.directorio_descarga = directorio_descarga
        os.makedirs(directorio_descarga, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; LoPublico/1.0)'
        })

    def descargar_archivo(self, tipo: str, fuente: str, anio: int, mes: Optional[int] = None,
                          silencioso: bool = False,  # evita prints cuando se llama desde threads paralelos
                          pbar_bytes=None) -> Optional[str]:  # barra externa opcional para acumular bytes totales
        """descarga un zip de PLACSP para el tipo/fuente/periodo dado"""
        if tipo not in self.CONFIGURACION_TIPOS:
            print(f"Tipo '{tipo}' no valido")
            return None
        config_tipo = self.CONFIGURACION_TIPOS[tipo]
        # la fuente agregacion solo existe para licitaciones
        if fuente not in config_tipo['fuentes']:
            print(f"Fuente '{fuente}' no disponible para {tipo}")
            return None
        config_fuente = config_tipo['fuentes'][fuente]

        if anio < config_fuente['desde']:
            print(f"  {tipo} ({fuente}) disponible desde {config_fuente['desde']}")
            return None

        anio_actual = datetime.now().year

        # año actual se descarga por meses, el resto por año completo
        if mes and config_tipo['permite_mensual'] and anio == anio_actual:
            periodo = f"{anio}{str(mes).zfill(2)}"
            periodo_legible = f"{anio}-{str(mes).zfill(2)}"
        else:
            periodo = periodo_legible = str(anio)

        nombre_archivo = config_fuente['archivo_patron'].format(periodo=periodo)
        url = f"{self.BASE_URL}/sindicacion_{config_fuente['codigo']}/{nombre_archivo}"

        directorio = os.path.join(self.directorio_descarga, tipo, periodo_legible, fuente)  # antes incluia un nivel 'historico/' intermedio que no aportaba nada
        os.makedirs(directorio, exist_ok=True)

        # Si .done existe el archivo ya se extrajo correctamente en una ejecucion anterior
        archivo_done = os.path.join(directorio, '.done')
        if os.path.exists(archivo_done):
            if not silencioso:
                print(f"  Ya existe: {nombre_archivo}")
            return directorio

        # zip sin .done: extraccion interrumpida en ejecucion anterior
        archivo_zip = os.path.join(directorio, nombre_archivo)
        if os.path.exists(archivo_zip):
            if zipfile.is_zipfile(archivo_zip):
                atoms = self._extraer_y_verificar(archivo_zip, directorio, silencioso)
                if atoms:
                    os.remove(archivo_zip)
                    open(archivo_done, 'w').close()
                    return directorio
            os.remove(archivo_zip)

        # Se escribe a .tmp y solo al terminar se renombra a .zip; si falla a medias no queda un zip corrupto
        archivo_tmp = archivo_zip + '.tmp'
        max_intentos = 3
        for intento in range(1, max_intentos + 1):
            try:
                if not silencioso:
                    sufijo = f" (intento {intento}/{max_intentos})" if intento > 1 else ""
                    print(f"  Descargando {periodo_legible} ({fuente}){sufijo}...")
                # 30s para conectar, 300 para leer — los zips anuales pueden superar 1 GB
                # verify=False porque PLACSP usa un certificado que a veces no valida bien
                response = self.session.get(url, timeout=(30, 300), stream=True, verify=False)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                with open(archivo_tmp, 'wb') as f, tqdm(
                    total=total_size, unit='B', unit_scale=True,
                    desc=f"  {periodo_legible}", disable=silencioso
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            if pbar_bytes is not None:
                                pbar_bytes.update(len(chunk))

                if not zipfile.is_zipfile(archivo_tmp):
                    file_size = os.path.getsize(archivo_tmp)
                    if not silencioso:
                        print(f"  Archivo invalido ({file_size} bytes)")
                    os.remove(archivo_tmp)
                    return None

                os.rename(archivo_tmp, archivo_zip)
                atoms = self._extraer_y_verificar(archivo_zip, directorio, silencioso)
                if not atoms:
                    os.remove(archivo_zip)
                    return None

                os.remove(archivo_zip)
                open(archivo_done, 'w').close()
                return directorio

            except Exception as e:
                if os.path.exists(archivo_tmp):
                    os.remove(archivo_tmp)
                # Solo reintentamos errores de red; cualquier otro (parsing, IO...) se propaga directamente
                if not isinstance(e, requests.exceptions.RequestException):
                    raise
                if intento < max_intentos:
                    espera = 10 * intento
                    if not silencioso:
                        print(f"  Error (intento {intento}): {e} — reintentando en {espera}s...")
                    time.sleep(espera)
                else:
                    if not silencioso:
                        print(f"  Error descargando tras {max_intentos} intentos: {e}")
                    return None

    def _extraer_y_verificar(self, archivo_zip: str, directorio_destino: str, silencioso: bool = False) -> List[str]:
        # Antes era _extraer_zip y devolvía bool; ahora también comprueba que haya .atom dentro,
        # porque PLACSP a veces devuelve un ZIP valido pero vacio o con solo un HTML de error
        try:
            with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
                zip_ref.extractall(directorio_destino)
        except Exception as e:
            print(f"  error extrayendo ZIP: {e}")
            return []

        atoms = [
            os.path.join(directorio_destino, f)
            for f in os.listdir(directorio_destino)
            if f.endswith('.atom')
        ]

        if not atoms:
            if not silencioso:
                print(f"  zip sin atoms: {os.path.basename(archivo_zip)}")
            return []

        return atoms
