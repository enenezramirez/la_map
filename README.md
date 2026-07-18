# Traza

**Inteligencia territorial · Zona Metropolitana de Saltillo**

Visualizador web de riesgos e inversión inmobiliaria. Cruza datos públicos de INEGI (Censo 2020, DENUE) y del Atlas de Riesgos del IMPLAN Saltillo para mostrar, por AGEB/colonia, la cobertura de servicios básicos, las zonas de riesgo natural y un índice de inversión inmobiliaria sobre un mapa interactivo.

Cubre **431 AGEBs en tres municipios**: Saltillo, Ramos Arizpe y Arteaga.

**Demo:** https://enenezramirez.github.io/la_map/

## Capas del mapa

- **Cobertura de Servicios Básicos** — cobertura de agua, luz, drenaje e internet por AGEB (Censo de Población y Vivienda 2020, INEGI).
- **Riesgo de Inundación** — zonas de riesgo por inundación pluvial urbana, por nivel de intensidad (Atlas de Riesgos 2024, IMPLAN Saltillo).
- **Riesgo de Deslizamientos** — zonas de riesgo por deslizamientos traslacionales en laderas, por nivel de intensidad (Atlas de Riesgos 2024, IMPLAN Saltillo).
- **Riesgo Químico-Tecnológico** — zonas expuestas al almacenamiento de sustancias químicas peligrosas, relevante en el corredor industrial Saltillo–Ramos Arizpe (Atlas de Riesgos 2024, IMPLAN Saltillo).
- **Índice de Inversión Inmobiliaria** — combina la cobertura de servicios con la cercanía a equipamiento urbano (escuelas, salud, supermercados del DENUE) y penaliza la exposición a inundación.

Haz clic en cualquier colonia o zona de riesgo del mapa para ver su ficha de detalle, con la fuente y la fecha de corte de los datos que estás viendo.

### Cómo leer los colores

Cada familia de color significa una sola cosa: **rojo-ladrillo = peligro**, **ámbar = valor** (índice de inversión) y **teal = cobertura** de servicios. Las rampas son secuenciales, así que también se leen en escala de grises y funcionan con daltonismo rojo-verde.

Los cortes del choropleth se calculan **por cuantiles** sobre los datos reales, no en escalones fijos: el color indica la **posición relativa** de un sector dentro de la ciudad, no una calificación absoluta.

Un sector en **gris** no es un sector malo: es un sector **sin dato**. Ocurre cuando no tiene viviendas habitadas, cuando el INEGI enmascaró sus cifras por confidencialidad (conteos de 1-2 viviendas) o cuando no aparece en el Censo. La ficha dice cuál de los tres es. Estos sectores tampoco reciben índice de inversión, porque les falta el 40% de su peso.

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
index.html           Mapa (Leaflet) y lógica de la interfaz
styles.css           Estilos (tema oscuro, tokens de diseño en :root)
assets/
  logo-traza.svg     Marca de vértice; también favicon
scripts/
  process_data.py    Pipeline de procesamiento de datos (GeoPandas)
data/
  servicios_basicos.geojson      Capa de servicios básicos por AGEB
  indice_inversion.geojson       Capa del índice de inversión por AGEB
  riesgo_inundacion.geojson      Capa de riesgo por inundación pluvial (IMPLAN)
  riesgo_deslizamientos.geojson  Capa de riesgo por deslizamientos (IMPLAN)
  riesgo_quimico.geojson         Capa de riesgo químico-tecnológico (IMPLAN)
  riesgo_inundacion.png          Raster de severidad del ANRI (respaldo) + su _meta.json
SPEC.md              Especificación técnica del proyecto
DATOS.md             Bitácora de datos: procedencia de cada dataset
task.md              Lista de tareas y estado de avance
```

Los datos crudos (`raw_data/`) no se incluyen en el repositorio por su tamaño; [DATOS.md](DATOS.md) documenta de dónde sale cada uno y `scripts/process_data.py` cómo se procesan.

## Fuentes de datos

Todas son fuentes oficiales y de acceso público. La procedencia completa —editor, fecha de corte, fecha de descarga, licencia y limitaciones de cada dataset, más los que se descartaron y por qué— está en la bitácora [DATOS.md](DATOS.md).

- [INEGI — Información vectorial de localidades amanzanadas y números exteriores 2023](https://www.inegi.org.mx/app/mapas/) (polígonos de AGEB y nombre de colonia)
- [INEGI — Censo de Población y Vivienda 2020](https://www.inegi.org.mx/programas/ccpv/2020/) (servicios básicos por AGEB)
- [INEGI — DENUE 05_2026](https://www.inegi.org.mx/app/mapa/denue/default.aspx) (escuelas, salud, supermercados)
- [IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024](https://implansaltillo.mx/perfil/) (riesgo por inundación pluvial, por deslizamientos traslacionales y químico-tecnológico)
- [CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI)](https://rmgir.proyectomesoamerica.org/server/rest/services/ANRI/RegionNoreste_ANRI/MapServer) (raster de severidad, Tr = 100 años; se conserva como respaldo del IMPLAN)

## Estado del proyecto

Las cinco capas están en funcionamiento sobre los 431 AGEBs de los tres municipios. Las capas de riesgo del IMPLAN, en cambio, **solo cubren Saltillo**: su Atlas es municipal, así que al navegar a Ramos Arizpe o Arteaga el panel deshabilita esas capas y lo explica en vez de mostrar un mapa vacío sin motivo.

Pendientes principales: la capa de riesgo forestal sigue sin fuente (relevante ahora que Arteaga aporta AGEBs en la sierra), y las capas de vulnerabilidad del IMPLAN están sin evaluar. El detalle completo está en [task.md](task.md).

Los datos de riesgo son modelos de intensidad a escala urbana: sirven para comparar zonas, no sustituyen un estudio de sitio.

El repositorio se llama `la_map` por razones históricas; `Traza` es el nombre del producto.
