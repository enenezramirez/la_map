# GeoRiesgos Saltillo

Visualizador web de riesgos e inversión inmobiliaria para Saltillo, Coahuila. Cruza datos públicos de INEGI (Censo 2020, DENUE) para mostrar, por AGEB/colonia, la cobertura de servicios básicos y un índice de inversión inmobiliaria sobre un mapa interactivo.

**Demo:** https://enenezramirez.github.io/la_map/

## Capas del mapa

- **Cobertura de Servicios Básicos** — % de viviendas con agua, luz, drenaje e internet (Censo de Población y Vivienda 2020, INEGI).
- **Índice de Inversión Inmobiliaria** — combina la cobertura de servicios con la cercanía a equipamiento urbano (escuelas, salud, supermercados del DENUE).
- **Riesgo de Inundación** — pendiente, no hay datos granulares de CENAPRED disponibles todavía (ver [task.md](task.md)).

Haz clic en cualquier colonia del mapa para ver su ficha de detalle.

## Stack

- **Frontend:** HTML/CSS/JavaScript vanilla + [Leaflet.js](https://leafletjs.com/), sin frameworks ni build step.
- **Procesamiento de datos:** Python (GeoPandas, pandas) para limpiar, cruzar y exportar los datos a GeoJSON.

## Correr el proyecto localmente

```bash
# 1. Entorno de Python (solo si vas a reprocesar los datos)
python -m venv venv
venv\Scripts\pip install pandas geopandas jupyter shapely pyproj

# 2. Regenerar los GeoJSON de data/ (opcional, ya vienen incluidos en el repo)
venv\Scripts\python scripts/process_data.py

# 3. Servir el sitio
python -m http.server 8000
```

Abre `http://localhost:8000` en tu navegador.

## Estructura

```
index.html          Mapa (Leaflet) y lógica de la interfaz
styles.css           Estilos (tema oscuro, glassmorphism)
scripts/
  process_data.py    Pipeline de procesamiento de datos (GeoPandas)
data/
  servicios_basicos.geojson   Capa de servicios básicos por AGEB
  indice_inversion.geojson    Capa del índice de inversión por AGEB
SPEC.md              Especificación técnica del proyecto
task.md              Lista de tareas y estado de avance
```

Los datos crudos descargados de INEGI/DENUE (`raw_data/`) no se incluyen en el repositorio por su tamaño; el pipeline en `scripts/process_data.py` documenta de dónde sale cada uno.

## Fuentes de datos

- [INEGI — Marco Geoestadístico](https://www.inegi.org.mx/app/mapas/) (polígonos de AGEB)
- [INEGI — Censo de Población y Vivienda 2020](https://www.inegi.org.mx/programas/ccpv/2020/) (servicios básicos por AGEB)
- [INEGI — DENUE](https://www.inegi.org.mx/app/mapa/denue/default.aspx) (escuelas, salud, supermercados)

## Estado del proyecto

El proyecto cubre únicamente el municipio de Saltillo por ahora. Ramos Arizpe, Arteaga y la capa de riesgo de inundación quedan pendientes por falta de datos disponibles — el detalle completo está en [task.md](task.md).
