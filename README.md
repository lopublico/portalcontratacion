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
python scripts/descargar.py l --a 2026 --m 1
python scripts/descargar.py cm --a 2026 --m 1
python scripts/descargar.py e --a 2025
python scripts/descargar.py cp --a 2025
python scripts/procesar_todo.py --parquet
```

## API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
# docs en http://localhost:8000/docs
```