# Portal de contratación publica

Extrae datos de PLACSP, los procesa y los publica via API.

## Estructura

- `etl/` — descarga y procesado de datos
- `api/` — API REST sobre los datos procesados
- `portal/` — interfaz web

## ETL

```bash
cd etl
pip install -r requirements.txt

# descarga completa + parquet
python scripts/descargar.py

# solo descarga o solo procesado
python scripts/descargar.py --solo-descargar
python scripts/descargar.py --solo-procesar

# tipo concreto: l=licitaciones  cm=menores  e=encargos  cp=consultas
python scripts/descargar.py l                 # licitaciones, historico completo
python scripts/descargar.py l --a 2024        # licitaciones, solo 2024
python scripts/descargar.py l --a 2026 --m 3  # licitaciones, marzo 2026
python scripts/descargar.py cm --a 2026 --m 1 # menores, enero 2026
python scripts/descargar.py e --a 2025        # encargos, 2025

# procesado manual
python scripts/procesar.py --parquet
python scripts/procesar.py --forzar --parquet
```

## Tiempos estimados (descarga completa)

| Tipo | Periodo | Archivos .atom | Registros brutos | Registros (post-dedup) | JSONL | CSV | Descarga | Parseo | Deduplicación | Parquet |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| licitaciones | 2012–2026 | 12.345 | 5.735.827 | 1.598.781 | 4,1 GB | 2,0 GB | 85m | 24m | 38m | 318 MB |
| menores | 2018–2026 | 7.062 | 3.487.031 | 3.397.400 | 8,2 GB | 3,7 GB | 9m | 9m | 1m | 493 MB |
| encargos | 2022–2026 | 35 | 15.930 | 13.577 | 28 MB | 19 MB | 7s | 2s | <1s | 2,4 MB |
| consultas | 2022–2026 | 9 | 3.915 | 2.140 | 4,9 MB | 3,8 MB | 2s | <1s | <1s | 643 KB |
| **Total** | **2012–2026** | **19.451** | **9.242.703** | **5.011.898** | **~13 GB** | **~5,7 GB** | **~95m** | **~33m** | **~39m** | **814 MB** |

Los tiempos son aproximados y pueden variar según el estado del servidor de PLACSP y las características del equipo.

## API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
# docs en http://localhost:8000/docs
```