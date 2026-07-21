# Traza

**Territorial intelligence · Saltillo Metropolitan Area**

Web visualizer for real-estate risk and investment. It combines public data from INEGI (2020 Census, DENUE) and the IMPLAN Saltillo Risk Atlas to show, per AGEB/colonia, basic-service coverage, natural-risk zones and a real-estate investment index on an interactive map.

Covers **431 AGEBs across three municipalities**: Saltillo, Ramos Arizpe and Arteaga.

**Demo:** https://enenezramirez.github.io/la_map/

## Map layers

- **Basic Services Coverage** — water, electricity, sewage and internet coverage per AGEB (2020 Population and Housing Census, INEGI).
- **Flood Risk** — urban pluvial flood risk zones, by intensity level (2024 Risk Atlas, IMPLAN Saltillo).
- **Landslide Risk** — translational hillside landslide risk zones, by intensity level (2024 Risk Atlas, IMPLAN Saltillo).
- **Chemical-Technological Risk** — zones exposed to the storage of hazardous chemical substances, relevant along the Saltillo–Ramos Arizpe industrial corridor (2024 Risk Atlas, IMPLAN Saltillo).
- **Real-Estate Investment Index** — combines service coverage with proximity to urban amenities (schools, healthcare, supermarkets from DENUE) and penalizes flood exposure.

Click any colonia or risk zone on the map to see its detail card, with the source and cutoff date of the data you are viewing.

### How to read the colors

Each color family means exactly one thing: **brick-red = danger**, **amber = value** (investment index) and **teal = coverage** of services. The ramps are sequential, so they also read in grayscale and work for red-green color blindness.

The choropleth breaks are computed **by quantiles** over the real data, not on fixed steps: the color indicates a sector's **relative position** within the city, not an absolute score.

A sector shown in **gray** is not a bad sector: it is a sector **without data**. This happens when it has no inhabited dwellings, when INEGI masked its figures for confidentiality (counts of 1-2 dwellings) or when it does not appear in the Census. The detail card states which of the three applies. These sectors also receive no investment index, because they are missing 40% of its weight.

## Stack

- **Frontend:** vanilla HTML/CSS/JavaScript + [Leaflet.js](https://leafletjs.com/), no frameworks or build step.
- **Data processing:** Python (GeoPandas, pandas) to clean, cross-reference and export the data to GeoJSON.

## Running the project locally

```bash
# 1. Python environment (only if you are going to reprocess the data)
python -m venv venv
venv\Scripts\pip install pandas geopandas jupyter shapely pyproj

# 2. Regenerate the GeoJSON files in data/ (optional, they are already included in the repo)
venv\Scripts\python scripts/process_data.py

# 3. Serve the site
python -m http.server 8000
```

Open `http://localhost:8000` in your browser.

## Structure

```
index.html           Map (Leaflet) and interface logic
styles.css           Styles (dark theme, design tokens in :root)
assets/
  logo-traza.svg     Vertex mark; also the favicon
scripts/
  process_data.py    Data processing pipeline (GeoPandas)
data/
  servicios_basicos.geojson      Basic-services layer per AGEB
  indice_inversion.geojson       Investment-index layer per AGEB
  riesgo_inundacion.geojson      Pluvial flood-risk layer (IMPLAN)
  riesgo_deslizamientos.geojson  Landslide-risk layer (IMPLAN)
  riesgo_quimico.geojson         Chemical-technological risk layer (IMPLAN)
  riesgo_inundacion.png          ANRI severity raster (backup) + its _meta.json
SPEC.md              Project technical specification
DATOS.md             Data log: provenance of each dataset
task.md              Task list and progress status
```

The raw data (`raw_data/`) is not included in the repository because of its size; [DATOS.md](DATOS.md) documents where each dataset comes from and `scripts/process_data.py` how they are processed.

## Data sources

All are official, publicly accessible sources. The complete provenance —publisher, cutoff date, download date, license and limitations of each dataset, plus the ones that were discarded and why— is in the [DATOS.md](DATOS.md) log. (Official dataset titles are kept in Spanish, as published.)

- [INEGI — Información vectorial de localidades amanzanadas y números exteriores 2023](https://www.inegi.org.mx/app/mapas/) (AGEB polygons and colonia name)
- [INEGI — Censo de Población y Vivienda 2020](https://www.inegi.org.mx/programas/ccpv/2020/) (basic services per AGEB)
- [INEGI — DENUE 05_2026](https://www.inegi.org.mx/app/mapa/denue/default.aspx) (schools, healthcare, supermarkets)
- [IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024](https://implansaltillo.mx/perfil/) (pluvial flood, translational landslide and chemical-technological risk)
- [CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI)](https://rmgir.proyectomesoamerica.org/server/rest/services/ANRI/RegionNoreste_ANRI/MapServer) (severity raster, Tr = 100 years; kept as an IMPLAN backup)

## Project status

All five layers are operational across the 431 AGEBs of the three municipalities. The IMPLAN risk layers, however, **only cover Saltillo**: its Atlas is municipal, so when navigating to Ramos Arizpe or Arteaga the panel disables those layers and explains why, instead of showing an empty map for no apparent reason.

Main pending items: the forest-fire risk layer still lacks a source (relevant now that Arteaga contributes AGEBs in the sierra), and the IMPLAN vulnerability layers are unevaluated. The full detail is in [task.md](task.md).

The risk data are urban-scale intensity models: they help compare zones, they do not replace a site study.

The repository is named `la_map` for historical reasons; `Traza` is the product name.
