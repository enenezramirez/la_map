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
- **Mapped Stream Courses** — the main arroyos (Strahler order 5 and up) as INEGI captured them in 1998–2008, before much of the current urban growth. Context only: not a risk classification and not part of any index.

Click any colonia or risk zone on the map to see its detail card, with the source and cutoff date of the data you are viewing.

**Find zones by criteria.** A panel filters the sectors by service coverage, pluvial flood exposure, straight-line distance to the nearest school, healthcare service and supermarket, and cadastral land value, then lists the matches and says why each one matched and where every value comes from. A sector with no figure for a criterion never matches: it is counted apart, because having no data is not meeting the criterion. It filters on the place only, never on who lives there, and it is deterministic — no AI and no requests beyond the files the map already loads.

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
venv\Scripts\pip install pandas geopandas jupyter shapely pyproj "pyogrio==0.12.0"

# 2. Regenerate the GeoJSON files in data/ (optional, they are already included in the repo)
venv\Scripts\python scripts/process_data.py

# 3. Serve the site
python -m http.server 8000
```

Open `http://localhost:8000` in your browser.

### Basemap and your own CARTO key

CARTO now requires an API key for its basemaps; without one, every basemap tile carries an **"API KEY REQUIRED" watermark**. The data layers are not affected. **This repository ships no key and never will** — it is public, and anything served to the browser is published — so out of the box the basemap shows the watermark.

To see the clean basemap, get your own free key at [carto.com/basemaps/apikey](https://carto.com/basemaps/apikey) (no account needed; at the time of writing, up to 5M requests a month for non-commercial use) and paste it in the panel under **Mapa base → Usar mi propia llave de CARTO**. It is kept only in your browser's `localStorage` (key `traza.cartoKey`), sent only to CARTO as `?key=` on the tile requests, and removed with **Quitar**. Anyone using the same browser profile — and any page served from the same origin, which on GitHub Pages is every project site of the same account — can read it, so treat it as your own quota, not as a secret.

> **Why `pyogrio` is pinned.** GeoPandas reads shapefiles and writes GeoJSON through
> `pyogrio`, which ships GDAL as bundled DLLs. Those DLLs are unsigned, so on Windows with
> **Smart App Control** enforcing, the loader admits them only once they have reputation.
> The DLLs in **0.13.0 do not have it yet and are blocked** — `pyogrio` then reports the
> misleading `GDAL DLL could not be found`, while the real cause appears in Event Viewer
> under `Microsoft-Windows-CodeIntegrity/Operational` as
> `An Application Control policy has blocked this file`. **0.12.0 loads.** Same story for
> `rasterio` (used only by the archived AlphaEarth scripts): pin **1.5.0**, not 1.5.1.
> This is a reputation gate, not a code defect: nothing here needs `pyogrio` 0.13.
>
> **Retry before concluding a version is blocked.** Reputation is not a stable verdict: on
> 2026-09-16 the pinned `rasterio` 1.5.0 was blocked once (`libpng16-*.dll`, same log) and
> imported normally a few minutes later, with nothing changed. And do not test a build by
> copying its DLLs elsewhere and loading them: that day the copies of the blocked DLLs
> loaded fine, so the test cannot tell a blocked build from a good one.

## Structure

```
index.html           Markup, Content-Security-Policy, asset loading
app.js               Application logic: map, layers, legends, search, cards
styles.css           Styles (dark theme, design tokens in :root)
assets/
  logo-traza.svg     Vertex mark; also the favicon
  fonts/             Self-hosted Inter and IBM Plex Mono (.woff2) + licenses
  vendor/
    leaflet-1.9.4/   Leaflet, vendored so no CDN sits in the render path
scripts/
  process_data.py    Data processing pipeline (GeoPandas)
data/
  servicios_basicos.geojson      Basic-services layer per AGEB
  indice_inversion.geojson       Investment-index layer per AGEB
  riesgo_inundacion.geojson      Pluvial flood-risk layer (IMPLAN)
  riesgo_deslizamientos.geojson  Landslide-risk layer (IMPLAN)
  riesgo_quimico.geojson         Chemical-technological risk layer (IMPLAN)
  riesgo_inundacion.png          ANRI severity raster (backup) + its _meta.json
  calles.json                    Street index (street -> settlement -> AGEB), fetched on first search
  valor_catastral.json           Cadastral land value per AGEB (informational, not in the index)
  cauces_inegi.geojson           Main stream courses, INEGI 1:50 000 (context, not a risk layer)
DATOS.md             Data log: provenance of each dataset
```

The raw data (`raw_data/`) is not included in the repository because of its size; [DATOS.md](DATOS.md) documents where each dataset comes from and `scripts/process_data.py` how they are processed.

## Data sources

All are official, publicly accessible sources. The complete provenance —publisher, cutoff date, download date, license and limitations of each dataset, plus the ones that were discarded and why— is in the [DATOS.md](DATOS.md) log. (Official dataset titles are kept in Spanish, as published.)

- [INEGI — Información vectorial de localidades amanzanadas y números exteriores 2023](https://www.inegi.org.mx/app/mapas/) (AGEB polygons and colonia name)
- [INEGI — Censo de Población y Vivienda 2020](https://www.inegi.org.mx/programas/ccpv/2020/) (basic services per AGEB)
- [INEGI — DENUE 05_2026](https://www.inegi.org.mx/app/mapa/denue/default.aspx) (schools, healthcare, supermarkets)
- [IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024](https://implansaltillo.mx/perfil/) (pluvial flood, translational landslide and chemical-technological risk)
- [CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI)](https://rmgir.proyectomesoamerica.org/server/rest/services/ANRI/RegionNoreste_ANRI/MapServer) (severity raster, Tr = 100 years; kept as an IMPLAN backup)
- [INEGI — Red Hidrográfica escala 1:50 000, edición 2.0](https://www.inegi.org.mx/temas/hidrografia/) (main stream courses, as context only)

## Project status

All five layers are operational across the 431 AGEBs of the three municipalities. The IMPLAN risk layers, however, **only cover Saltillo**: its Atlas is municipal, so when navigating to Ramos Arizpe or Arteaga the panel disables those layers and explains why, instead of showing an empty map for no apparent reason.

Main pending items: the forest-fire risk layer still lacks a source (relevant now that Arteaga contributes AGEBs in the sierra), and the IMPLAN vulnerability layers are unevaluated.

The risk data are urban-scale intensity models: they help compare zones, they do not replace a site study.

The repository is named `la_map` for historical reasons; `Traza` is the product name.
