# Data Log: Traza

Provenance record for every dataset used in the project. Because the analysis feeds
real-estate decisions, each layer must be traceable to its official source, its cutoff
date and the date we downloaded it — this is the project's data-legitimacy-and-traceability
requirement.

**How this log was filled in:** publication dates and official titles were taken from the
metadata shipped inside each downloaded package (INEGI `metadatos/*.txt` files and the
shapefiles' `*.shp.xml`), not from memory. Download dates come from the timestamps of the
folders under `raw_data/`. When a value could not be verified, that is stated explicitly
instead of estimating it.

**Last updated:** 2026-07-22

---

## 1. Summary

| # | Dataset | Publisher | Cutoff / edition | Downloaded | Status |
|---|---------|-----------|------------------|------------|--------|
| 1 | Información vectorial de localidades amanzanadas y números exteriores 2023 | INEGI | 2023-12-15 | 2026-07-08 | In use |
| 2 | Censo de Población y Vivienda 2020 (AGEB y manzana urbana, Coahuila) | INEGI | 2021-07-26 | 2026-07-08 | In use |
| 3 | DENUE 05_2026 (Coahuila) | INEGI | 2026-05-20 | 2026-07-08 | In use |
| 4 | Riesgo por inundaciones pluviales urbanas (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-15 | In use |
| 5 | Riesgo por deslizamientos traslacionales (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-15 | In use |
| 6 | Riesgo químico-tecnológico (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-17 | In use |
| 7 | ANRI — Severidad por inundación, Tr = 100 años | CONAGUA | Not published | 2026-07-16 | Backup |
| 8 | Riesgo por deslizamientos rotacionales (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-17 | Evaluated, not published |
| 9 | Indicadores Municipales PEV | CENAPRED | — | 2026-07-08 | Discarded |
| 10 | Susceptibilidad a inundaciones pluviales | IMPLAN Saltillo | 2024 | 2026-07-15 | Discarded |
| 11 | Tablas de Valores de Suelo y Construcción 2026 | Tesorería Municipal de Saltillo | 2026 | 2026-08-03 | In use |
| 12 | Satellite Embedding (AlphaEarth Foundations) | Google / Google DeepMind | 2017–2025, annual | Not downloaded | Evaluated, screening pending |

---

## 2. Datasets in use

### 2.1 INEGI — Información vectorial de localidades amanzanadas y números exteriores 2023

Provides the AGEB polygons (the base territorial unit of the whole analysis) and the
colonia name of each one.

* **Official title:** *Información vectorial de localidades amanzanadas y números
  exteriores 2023. 050300001 (SALTILLO).*
* **Publisher:** Instituto Nacional de Estadística y Geografía (INEGI).
* **Dates (product metadata):** created 2023-10-02, revised 2023-10-16,
  **published 2023-12-15**. Annual update.
* **Download date:** 2026-07-08.
* **Local path:** `raw_data/marco_geoestadistico/saltillo_map_ageb/` (one folder per
  locality: `050300001` Saltillo city + 3 rural localities).
* **Collection:** *Información vectorial de localidades amanzanadas y números exteriores*.
  **Edition: 2023.** Temporal coverage: 2011-01-01 to 2023-09-30.
* **Download site:** INEGI's digital Map Library
  (<https://www.inegi.org.mx/app/mapas/>), one downloadable record per locality.
* **License:** INEGI Free Use of Information terms
  (<https://www.inegi.org.mx/inegi/terminos.html>).
* **Use in the project:** AGEB layer (`filtrar_agebs_por_municipio`); colonia name
  per AGEB, derived from the block-front layer (`fm`, field `NOMASEN`) by taking the most
  frequent settlement in each AGEB (`cargar_nombres_colonias`); and the street index
  behind the search (`construir_indice_calles`, see below).
* **Street index — the `fm` layer, and why the `v` layer is not used.** Each `fm` record
  is one side of a block and already carries the street it faces (`NOMVIAL`, `TIPOVIAL`),
  the settlement it belongs to (`NOMASEN`) and its postal code (`CP`) **in the same row**,
  so pairing a street with its settlement needs no spatial work at all. The package also
  ships a `v` (vialidades) layer with 11,202 street *lines*; it is deliberately left
  unused, because the geometry it would add buys nothing the AGEB polygons already on the
  map do not already give, and it would cost file weight the map layers need more (SPEC §2).
  The exported index therefore carries **no geometry**: each zone lists the AGEB keys it
  touches, and the browser resolves position from the polygons it has already loaded.
  Output: `data/calles.json`, 6,597 street names, 13,877 street-settlement zones, ~429 KB,
  fetched lazily on the first search.
* **Filler values in `NOMVIAL` and `TIPOVIAL`.** As with `NOMASEN`, these fields carry
  markers that are not names: `NOMVIAL` uses **`NINGUNO`** (6,578 fronts), **`OTRO`**
  (2,377) and **`MANZANA O EDIFICACIÓN CONTIGUA`** (938) to describe what a front faces
  when it is not a street, and `TIPOVIAL` uses **`RASGO`** (3,810 — a physical feature such
  as an arroyo or a railway, which is where names like "MALEZA" come from) and
  **`SIN REFERENCIA`** (143). Left in, they dominate the index: `OTRO` alone would appear
  in 401 settlements, more than any real street in the city. See `VALORES_SIN_VIALIDAD` and
  `TIPOS_NO_VIALIDAD` in `scripts/process_data.py`.
* **Several settlements per street inside one AGEB — merged, not dropped.** INEGI records
  different `NOMASEN` values on different fronts of the *same* street inside the *same*
  AGEB, so the index would offer two or more "tramos" that resolve to identical sectors:
  1,553 groups, 14.5% of zones (worst case `CAMINO ANTIGUO A LOS RAMONES`, **seven**
  settlement names in one sector). Since the AGEB is the unit every figure is published
  at, those are one answer and not several, so they are merged into a single zone that
  carries **all** the names; the app states them on the card. The road type stays out of
  the merge — a `CALLE` and a `PRIVADA` of the same name in the same sector are two
  different roads (519 groups). The municipality cannot differ within a group (verified:
  0), because the sectors determine it.
* **Typos in `NOMVIAL` produce near-duplicate street names, and are left alone.** Example:
  `NICOLÁS BRAVO` and `NICÓLAS BRAVO` (accent on the wrong vowel) both exist and stay as
  two separate entries, because the raw strings differ. The search folds accents, so both
  are reachable from the same query. **They are deliberately not "corrected":** rewriting a
  source value would be inventing data, the same rule applied to `NOMASEN` fillers.
* **Measured: a front's own `NOMASEN` and its AGEB's published colonia disagree 42.1% of
  the time** (27,044 of 64,234 street fronts). This is the same 1:1 limitation noted below,
  quantified: an AGEB routinely spans several settlements and the map keeps the dominant
  one. The street index groups by the front's own settlement — the precise answer to "where
  is this street?" — and the app's card states the difference when the sector is published
  under another colonia, rather than hiding it.
* **Known limitation:** the AGEB is a statistical unit and does not match a colonia 1:1.
  The name is the *dominant* settlement among the AGEB's block fronts, not an official
  colonia boundary: a single AGEB can span several.
* **Filler values in `NOMASEN`:** the field uses **`ND`** (not available; its `TIPOASEN`
  also reads `ND`, 363 fronts) and **`NINGUNO`** (front with no assigned settlement, 141
  fronts) as markers, not as names. They must be discarded before computing the dominant
  settlement: an AGEB with 5 `NINGUNO` fronts and 4 with a real name would end up called
  "NINGUNO". See `VALORES_SIN_ASENTAMIENTO` in `scripts/process_data.py`. **Be careful
  when extending the list:** not every short or odd value is filler — `GIS` is a real name
  (Sector GIS, after Grupo Industrial Saltillo).
* **Current coverage (2026-07-17):** 3 municipalities, **431 AGEBs** — Saltillo (342),
  Ramos Arizpe (61) and Arteaga (28), the Metropolitan Area targeted by the project scope.
  Downloaded per municipality (packages `05004`/`05027`, product `vla_ne_mg_2022`) and
  reorganized into `arteaga_map_ageb/` and `ramos_arizpe_map_ageb/` (same pattern as
  `saltillo_map_ageb/`). Localities with an AGEB layer: `050040001` Arteaga seat,
  `050040107` San Antonio de las Alazanas (sierra) and `050270001` Ramos Arizpe city; the
  rest of the localities in each package are rural without AGEBs (skipped gracefully).
  428/431 AGEBs with census data (3 without a match, probably non-residential); 0 with
  `SIN_COLONIA`.

> **Attribution correction.** This product used to be cited as the *"Marco
> Geoestadístico"*. **It is not**, although the confusion is understandable: INEGI files it
> under the **theme** "Marco Geoestadístico" and it downloads from the same portal. But it
> is a distinct product that *uses* the Marco Geoestadístico (December 2022 edition) as a
> base layer, together with GEODOM 2010-2016, the 2017-2023 Urban and Rural Cartography,
> the 2019 Economic Censuses and the 2020 Census. Always cite it with the title and edition
> from this section. Corrected across the project's docs and `scripts/process_data.py`. The
> `raw_data/marco_geoestadistico/` folder keeps the old name on purpose: renaming it would
> break local copies of unversioned data for no gain.

### 2.2 INEGI — Censo de Población y Vivienda 2020 (AGEB and urban block)

* **Official title:** *Principales resultados por AGEB y manzana urbana del Censo de
  Población y Vivienda 2020. Datos oportunos* — Coahuila de Zaragoza state.
* **Identifier:** `MEX-INEGI.ESD2.01-CPV-2020`.
* **Publisher:** INEGI. Information of National Interest (SNIEG).
* **Census cutoff date:** 2020. **File last modified: 2021-07-26** (AGEBs and blocks of
  urban localities under 2,500 inhabitants were added).
* **Download date:** 2026-07-08.
* **Local path:** `raw_data/ageb_mza_urbana_05_cpv2020_csv/.../conjunto_de_datos_ageb_urbana_05_cpv2020.csv`.
* **License:** INEGI Free Use of Information terms.
* **Use in the project:** basic-service coverage per AGEB — `VPH_C_ELEC` (electricity),
  `VPH_AGUADV` (water), `VPH_DRENAJ` (sewage) and `VPH_INTER` (internet), all over
  `TVIVHAB`, plus the composite `SERVICIOS_INDEX`.
* **Known limitation:** being aggregated per AGEB, the Census **does not allow** computing
  the share of dwellings with *all* services simultaneously (that would require
  microdata). `SERVICIOS_INDEX` is the average of the four, an approximation.
* **Handling of missing values (reviewed 2026-07-18).** INEGI masks counts of 1-2
  dwellings with `*` for confidentiality. Until this date those asterisks were turned into
  `0`, and an AGEB with no inhabited dwellings also ended up at `0%`: the map painted
  **21 of 431 AGEBs as if they had the city's worst coverage when they were actually
  unmeasured**, and the error propagated into the Investment Index (those AGEBs got indices
  from 5.9 to 35.7 against a median of 86.1). Now "no data" is distinguished from "zero",
  with three reasons recorded in the `MOTIVO_SIN_DATO` field:
  * **No inhabited dwellings** (`TVIVHAB = 0`): 12 AGEBs. There is no one to serve.
  * **Figures masked by INEGI** (all 4 columns with `*`): 6 AGEBs, e.g. the UAAAN
    (3 dwellings) and the military zone (2).
  * **Not recorded in the 2020 Census** (the AGEB does not appear in the CSV): 3 AGEBs.

  **Partial masking** (1-3 of 4 columns, 5 AGEBs) *is* computed: the asterisk means 1-2
  dwellings out of a much larger total, so treating that column as 0% approximates reality
  rather than discarding the whole AGEB. After the change there is **a single genuine zero**
  left in the whole city (CENTRO METROPOLITANO, 26 inhabitants in 5 dwellings, with all
  four columns published as effectively zero). AGEBs without data are kept in the layers —
  painted gray, with the detail card explaining the reason — instead of vanishing from the
  map, which was the previous behavior of the `dropna` on export.

### 2.3 INEGI — DENUE 05_2026 (Coahuila)

* **Official title:** *Directorio Estadístico Nacional de Unidades Económicas (DENUE)
  05_2026.*
* **Identifier:** `MEX-INEGI.EEC2.05-DENUE-2026`.
* **Publisher:** INEGI.
* **Cutoff / modification date: 2026-05-20.** Annual update.
* **Download date:** 2026-07-08.
* **Download site:** <https://www.inegi.org.mx/app/descarga/?ti=6>.
* **Local path:** `raw_data/denue_05_csv/conjunto_de_datos/denue_inegi_05_.csv`.
* **License:** INEGI Free Use of Information terms.
* **Use in the project:** the "Amenities" component of the Investment Index — schools
  (SCIAN 61), healthcare (SCIAN 62) and supermarkets (by business-name matching, since they
  have no SCIAN sector of their own), measured as the distance from the AGEB centroid to
  the nearest establishment of each category.

### 2.4 IMPLAN Saltillo — Riesgo por inundaciones pluviales urbanas (Atlas de Riesgos 2024)

**Primary source of hydrometeorological risk** (Layer 1).

* **Official source:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Download site:** <https://implansaltillo.mx/perfil/> (CARTO SALTILLO portal; serves the
  layers in SHP, KML and PDF).
* **Cutoff date:** **2024**, per the portal label ("Atlas de Riesgos 2024").
* **Download date:** 2026-07-15.
* **Local path:** `raw_data/Riesgo_por_inundaciones_pluviales3/`.
* **Format:** shapefile, 12,679 records, EPSG:6372 (MEXICO_ITRF_2008_LCC).
* **Fields:** `Titulo`, `Intensid_1` (intensity level), `Detall`, `Fenom`.
* **Shapefile internal title:** `R050300001_R_INUNDACION_PLUVIAL`.
* **License / conditions:** the portal offers public access to the information and
  disclaims IMPLAN from liability for misuse of the data.
* **Use in the project:** layer `data/riesgo_inundacion.geojson` and the risk penalty of
  the Investment Index (`RIESGO_INDEX`, via an AGEB↔risk overlay in EPSG:6372).
* **Method behind it (established 2026-08-03):** the Atlas was produced with UNAM's Instituto
  de Geografía and **does** use elevation — LiDAR, soil permeability and composition, riverbed
  morphology, and hydrological scenarios by return period (5/25/50/100/500 years). This
  settles a question that had been open in `task.md`: the model is not 2D exposure only, so
  layering our own DEM on top would duplicate, less rigorously, work already done.

#### Documented limitation: colonias that flooded are not classed as high risk

**This is the most serious caveat attached to any layer in this project, and it is measured,
not inferred.** *Vanguardia* reported (2025-07-24) that colonias flooded in July 2025 were
classed low or very low by this same 2024 Atlas — Omega reaching 1.3 m of water, Terranova
1 m, plus Nazario Ortiz Garza, Country Club, Lomas del Refugio and others.

Checked against **the file this project publishes**, by overlaying those colonias' AGEBs on
`data/riesgo_inundacion.geojson`:

| Colonia (flooded, July 2025) | What our layer shows |
|---|---|
| **OMEGA** (1.3 m) | **no mapped flood zone at all — 0% of its area** |
| TERRANOVA (1 m) | 13% of its area, `Bajo` only |
| COUNTRY CLUB | 61%, all `Bajo` |
| LOMAS DEL REFUGIO | 7%, mostly `Bajo` |
| VALENCIA · LA AURORA | 39% / 54%, `Bajo` only |
| ZONA CENTRO | 2% |

**Not one of the 16 named colonias has a single square metre classed `Alto` or `Muy alto`.**
The highest level reached anywhere among them is `Medio`, over 6–13% of the area. Note also
that the export drops `Muy bajo`, so a colonia the Atlas placed in that class renders as
completely clean — which is exactly what happens to Omega.

**What this does and does not establish.** It establishes that the published classification
under-represents flooding that actually occurred, in specific named places, one year after
the Atlas edition. It does **not** establish why: the return period modelled, drainage works
or construction after the study, and the difference between *pluvial* flooding and flooding
from arroyos are all candidates, and nothing here distinguishes them. IMPLAN was integrating
a separate *plan pluvial* as of Nov 2024.

**Consequence for the product, acted on 2026-08-03.** The existing glossary line — "a model
at urban scale, not a site study" — is true but too soft for this. A reader comparing zones
would take a blank map as evidence of safety, and in Omega's case that reading is contradicted
by an event. The flood layer's legend now carries the caveat in two places: a pinned line next
to the ramp (**absence of a mapped zone is not evidence of absence of flooding**, plus the
July 2025 episode in one clause), and the episode in full inside the layer's help — the
colonias, the depths, the fact that dropping `Muy bajo` renders such a colonia clean, and
what this does and does not establish. Only this layer carries it; the other two risk layers
have no measured counter-example, and a caveat printed everywhere would say nothing anywhere.

### 2.5 IMPLAN Saltillo — Riesgo por deslizamientos traslacionales (Atlas de Riesgos 2024)

**Primary source of geological risk** (Layer 4).

* **Official source:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Authorship credit (shapefile metadata):** **Instituto de Geografía de la UNAM**
  (`idCredit: "IGg. UNAM"`). The flood shapefile carries no credit.
* **Download site:** <https://implansaltillo.mx/perfil/>.
* **Cutoff date:** 2024 (portal label).
* **Download date:** 2026-07-15.
* **Local path:** `raw_data/Riesgo_por_Deslizamientos_traslacionales2/`.
* **Format:** shapefile, 12,679 records, EPSG:6372.
* **Fields:** `Titulo`, `Intensid_1`, `Detalle`, `Fenome`.
* **Shapefile internal title:** `R05030_RIESGO_PRM_DESLIZAMIENTOS_TRASLACIONALES_TR2_MZ`.
* **Use in the project:** layer `data/riesgo_deslizamientos.geojson`.

> **On the dates of the two IMPLAN layers.** The files internally declare modification
> 2025-02-27 and creation 2025-04-01/02, later than the portal's "2024" label. These are
> interpreted as file-export dates, not the Atlas edition date, so **the cutoff date
> published in the app remains 2024**, which is how the publisher names the product
> (`IMPLAN_FECHA_CORTE` in `scripts/process_data.py`). Worth confirming with IMPLAN if
> month-level precision ever matters.

### 2.6 IMPLAN Saltillo — Riesgo químico-tecnológico (Atlas de Riesgos 2024)

**Primary source of anthropogenic risk**, highly relevant along the Saltillo–Ramos Arizpe
industrial corridor (GM, Stellantis, GIS).

* **Official source:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Download site:** <https://implansaltillo.mx/perfil/>.
* **Cutoff date:** 2024 (portal label).
* **Download date:** 2026-07-17.
* **Local path:** `raw_data/Riesgo_Quimico_tecnologico/`.
* **Format:** **polygon** shapefile (not points), 12,679 records, EPSG:6372 — the same grid
  as flood and landslides.
* **Fields:** `Titulo` ("Riesgo Químico-Tecnológico"), `Intensid_1` (Muy Bajo→Alto; no
  "Muy alto"), `Detalle` ("Riesgo por almacenamiento de sustancias químicas peligrosas"),
  `Fenome` ("Químico-Tecnológico").
* **Use in the project:** layer `data/riesgo_quimico.geojson`. **Informational only** (it
  does not penalize the Investment Index; like landslides, only flooding penalizes).
* **Its own threshold (Medium+High).** Unlike the other layers — which only drop "Muy
  bajo" — this one also drops **"Bajo"**: there that level covers 9,644 of 12,679 cells
  (93% of the grid), it is the model's background with no discriminating value, and keeping
  it would make the layer weigh **6.9 MB** (exceeding the project's 5 MB per-layer limit on
  its own). With Medium (1,937) + High (212) it comes to **1.28 MB / 2,136 zones**, showing
  only genuine exposure. The threshold lives in `NIVELES_ELEVADOS_QUIMICO`
  (`scripts/process_data.py`), passed to `preparar_capa_riesgo(niveles=...)`.

### 2.7 CONAGUA — ANRI, flood severity (Tr = 100 years) *(backup)*

Kept as an alternative source; **IMPLAN is the primary one** for being local, vectorial and
more recent. This dataset is raster and of coarser granularity.

* **Official source:** CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI), Northeast
  Region. Layer "Severity, 100-year return period" (Saltillo, Coahuila).
* **Service:** <https://rmgir.proyectomesoamerica.org/server/rest/services/ANRI/RegionNoreste_ANRI/MapServer/142>
  (ArcGIS REST, layer 142).
* **Download / query date:** 2026-07-15; re-downloaded on 2026-07-16 and the raster came
  back byte-identical, so the source has not changed between the two dates. The service
  publishes no cutoff date. `fecha_descarga` in `riesgo_inundacion_meta.json` is rewritten
  with the current date every time the pipeline runs.
* **Variable:** severity (a composite index of depth and velocity); high, medium and low
  classes.
* **Local path:** `data/riesgo_inundacion.png` + `data/riesgo_inundacion_meta.json`
  (a georeferenced PNG used as a Leaflet `imageOverlay`).
* **Generated by:** `descargar_raster_inundacion()` in `scripts/process_data.py`.
* **Official note:** an approximation from hydraulic modeling; it does not replace a site
  study.

### 2.8 Tesorería Municipal de Saltillo — Tablas de Valores de Suelo y Construcción 2026

The only dataset here published **per colonia by name**, which is the unit this project
already works in, so it joins with no geometry and no spatial operation at all. Published as
an **informational layer**: it does **not** enter the Investment Index — see the note at the
end for why that is a decision and not an omission.

* **Official source:** Tesorería Municipal de Saltillo, *Tablas de Valores de Suelo y
  Construcción*, approved by the Congreso del Estado de Coahuila de Zaragoza.
* **Portal:** Saltillo transparency, Article 28 §XIII (cuotas y tarifas).
* **Edition / fiscal year:** 2026. **Download date:** 2026-08-03 (13.96 MB PDF).
* **Local path:** `raw_data/catastro/TABLAS_VALORES_SUELO_CONSTRUCCION_2026.pdf` (gitignored,
  like all `raw_data/`).
* **Structure:** two tables. Colonia → *tipo de terreno*, and *tipo de terreno* → pesos per m².
  **14 terrain classes, 879 colonias.** `ZONA CENTRO` is excluded from the colonia table and
  priced by its own min/max table, so it is published here as having no figure.
* **Values in force (2026), pesos/m²:** LOCALIDAD (SOLAR) 60.20 · POPULAR (1) 263.18 ·
  INDUSTRIAL (1) 309.71 · POPULAR (2) and INDUSTRIAL (2) 464.45 · CAMPESTRE 483.52 ·
  ZONA TIPICA 557.12 · INTERES SOCIAL (1) 619.40 · INTERES SOCIAL (2) 712.05 ·
  MEDIO BAJO 866.99 · MEDIO MEDIO 1,021.73 · MEDIO ALTO 1,238.38 · RESIDENCIAL 1a 2,225.34 ·
  RESIDENCIAL DE LUJO 2,967.17.
* **Coverage achieved: 246 of 342 Saltillo AGEBs (71.9%)** — 227 matched exactly, 4 by equal
  word set, 15 by spacing alone. The remaining 96 are published as having no figure, with the
  reason stated in the card.
* **Matching is deliberately conservative.** Word-*subset* matching was measured and rejected:
  it would pair the map's `AMISTAD` with the cadastre's `AMISTAD III`, and a land value bound
  to the wrong colonia is worse than no value. Only exact folds, equal word sets
  (`RESIDENCIAL LOS LAGOS` = `LOS LAGOS RESIDENCIAL`) and spacing (`VISTA HERMOSA` =
  `VISTAHERMOSA`) are accepted, and the card discloses whenever the cadastre files the colonia
  under a differently written name.
* **Generated by:** `extraer_tablas_catastrales()`, `asignar_valor_catastral()` and
  `exportar_valor_catastral()` in `scripts/process_data.py`.
* **Two extraction traps, both measured:** the cell separator inside the PDF content streams is
  the document's language tag and **changes between editions** (`es-ES` in older ones, `es-MX`
  in 2026); and the class labels drift in the source itself (`RESIDENCIAL 1a.` vs
  `RESIDENCIAL 1a`, `RESIDENCIAL LUJO` vs `RESIDENCIAL DE LUJO`, `MEDIO MEDIO` vs
  `MEDIA MEDIA`), so they are normalised before the value lookup. Unnormalised, colonias fall
  through with no error at all.
* **Official note, carried into the file and the card because this product is aimed at
  buyers:** a cadastral value is a **tax base, not a market price**. It is set deliberately
  below market value in Mexico, and it is a *class assigned to a whole colonia*, not an
  appraisal of a property.
* **Why it is informational and not part of the Index (user's decision, 2026-08-03):** a *low*
  land value is genuinely ambiguous for a buyer — cheap entry or weak area — so unlike services
  (higher is better) and risk (higher is worse) it has no obvious sign, and giving it one would
  bake an undeclared thesis into the score.

---

## 3. Discarded datasets and evaluated sources

Documented so they are not re-evaluated from scratch.

### 3.1 CENAPRED — Indicadores Municipales PEV

* **Local path:** `raw_data/cenapred_indicadores_municipales/` (2,469 records, all of Mexico).
* **Download date:** 2026-07-08.
* **Reason for discarding:** **municipal resolution**. Its hazard fields
  (`GP_INUNDAC`, `SUSCEPLAD`, `GP_SISMICO`…) give a single value for the whole municipality
  of Saltillo, useless for distinguishing risk between colonias, which is exactly the app's
  purpose. Superseded by IMPLAN's vector layers.

### 3.2 IMPLAN — Susceptibilidad a inundaciones pluviales

* **Local path:** `raw_data/SUSCEPTIBILIDAD_INUNDACIONES_PLUVIALES/`
  (`S05030_SUSCEPTIBILIDAD_INUNDACIONES_PLUVIALES`).
* **Download date:** 2026-07-15.
* **Reason for discarding:** it measures **susceptibility** (the terrain's predisposition),
  not **risk** (which already incorporates exposure and vulnerability). The risk layer from
  the same Atlas is the right one for the app's purpose and would make them redundant.

### 3.2b IMPLAN — Riesgo por deslizamientos rotacionales (Atlas 2024) — downloaded, not published

* **Local path:** `raw_data/Riesgo_por_Deslizamientos_rotacionales3/` (12,679 polygons,
  EPSG:6372). **Download date:** 2026-07-17. Kept in case it is reconsidered.
* **Reason for not publishing it:** **marginal added value**. It is the sibling layer of
  the translational one we do use (§2.5), but its maximum intensity level is barely "Medium"
  (75 of 12,679 cells); the rest is background "Low"/"Very low". With the standard treatment
  it would weigh 2.3 MB of mostly "low", and keeping only "Medium" is 75 cells (~49 KB) of
  very weak signal. **It does not change an investment decision**, which is the bar for
  including a layer. Verified at the cell level against the translational layer (same grid):
  of its 3,882 elevated cells only 76 overlap the translational one, and its 75 "Medium"
  cells all fall where the translational layer sees "Very low" — i.e. it contributes
  different terrain, but of low intensity. **It is not merged with the translational one:**
  they are distinct failure mechanisms (planar vs. concave surface) with intensity scales
  that are not necessarily comparable; mixing them would create a derived layer with no
  source of its own and would break traceability.
* **Reactivation:** if geological-risk completeness is ever sought, add it as a **separate
  layer** (never merged), preferably only its "Medium" level.

---

### 3.3 Riesgo por incendios forestales (forest-fire risk, Layer 2) — evaluated and deferred

**No dataset was downloaded.** The layer was evaluated on 2026-07-16 and it was decided not
to implement it while the scope is urban Saltillo. This is not a final discard: it has a
reactivation criterion.

* **Sources considered:** CONABIO/CONAFOR, IMPLAN, CENAPRED.
* **Reasons for deferring:**
  1. **IMPLAN publishes no fire layer.** Its Atlas de Riesgos 2024 (CARTO SALTILLO) maps 7
     layers — rotational and translational landslides, urban pluvial flooding, flood
     susceptibility, hazardous-chemical storage, socio-organizational and
     sanitary-ecological vulnerability — and none is about fire. The municipality's
     planning institute, mapping the risks of its own territory, did not consider it
     relevant. This is the strongest evidence against.
  2. **There is no analysis unit where the hazard is.** The AGEB (§2.1) is urban and today
     only covers Saltillo. Fire hazard is in the sierra and in Arteaga, where there are no
     AGEBs: the layer would paint territory the app analyzes nothing about. Compare with the
     current risk layers, which fall 100% inside AGEB coverage (1095/1095 and 195/195
     verified representative points).
  3. **It would not discriminate in the Investment Index.** The penalty is computed by area
     intersection with each AGEB; if the hazard barely grazes the urban footprint, the
     result would be ≈0 for almost every sector. A variable that does not distinguish
     between zones adds nothing to the scoring and does cost file size, UI and maintenance.
  4. **The only source at hand is municipal.** CENAPRED's `GP_IF` field (§3.1) gives a
     single value for all of Saltillo: the same lack of granularity that already discarded
     that dataset.
* **Reactivation criterion:** implement it once the AGEBs of **Arteaga** exist within the
  project scope. There the risk is real — the wildland-urban interface at Los Lirios, San
  Antonio de las Alazanas and the Sierra de Zapalinamé — and there would be sectors to
  analyze. At that point a source must be sought again (CONAFOR/CONABIO, or Arteaga's risk
  atlas if one exists), since Saltillo's IMPLAN atlas does not cover that municipality.

### 3.4 Insecurity / crime incidence — investigated and deferred

User's idea: highly relevant to a real-estate decision (it weighs more than a 2nd type of
landslide). It was investigated thoroughly on **2026-07-17** and deferred for **lack of data
at a useful granularity**. This is not a final discard: it has a reactivation criterion.

* **No dataset was downloaded.** The problem is availability, not effort.
* **Sources reviewed and their granularity:**
  * **SESNSP** (national, official) — only **state and municipal**; nothing below the
    municipality outside Mexico City. A single value for all of Saltillo.
  * **Fiscalía General de Coahuila / Comisaría de Seguridad de Saltillo** — publish no
    incidence dataset per colonia. The Comisaría only offers **citizen-report** apps
    (Saltillo Seguro, a WhatsApp bot) and **perception** surveys.
  * **Observatories** (ONC `delitosmexico`, Semáforo Delictivo Coahuila, the Consejo
    Cívico's RID) — all municipal.
  * **`mapa.ocl.org.mx`** — this is the Citizen Observatory of **León, Guanajuato**
    (per-colonia data with .xlsx download), **not** Coahuila. It proves the per-colonia
    model exists in other cities, but it does not cover Saltillo.
  * **HoyoDeCrimen** — georeferenced per colonia but **exclusive to Mexico City**.
  * **El Crimen (`elcri.men`), `lapanquecita/incidencia-delictiva` (GitHub)** — the best
    community tool; it is fed by SESNSP, i.e. **municipal**.
* **Reason for deferring:** the same **granularity trap** that discarded CENAPRED (§3.1). A
  single municipal value does not discriminate between colonias → dead weight in the index.
  The cause is structural: SESNSP does not publish sub-municipal data outside Mexico City,
  which is why no community project has solved it for Saltillo.
* **Ethical consideration (for when it is reactivated):** crime data is biased by reporting
  rate, and a "dangerous colonias" choropleth in a real-estate scoring app affects the
  value of real people's property and can become a self-fulfilling prophecy. If implemented,
  it must use a verified official source, declare the bias in the detail card, and decide
  explicitly whether it enters the index or stays informational.
* **Reactivation criterion:** the only viable path is IMPLAN's **macrozone** — 12 polygons
  grouping AGEBs (defined since ~2017); the Comisaría analyzes insecurity by macrozone
  ("Oriente" is the least safe). It would integrate cleanly (same IMPLAN source, AGEB base),
  but **it is not open data today**: it would require an institutional request to IMPLAN or
  the Comisaría (a transparency request / municipal report with per-macrozone figures), not
  a web search.

---

### 3.5 Cadastral land value — investigated, and now PUBLISHED (see §2.8)

Kept here because the investigation is what established that this source was usable at all,
and the reasoning is worth not repeating. **The dataset itself is now in use: see §2.8.**

User's idea: land value is the single most relevant figure for the investor audience the
product is aimed at. Investigated **2026-07-27** (sources located), **2026-07-29** (format and
join measured on an older edition) and **2026-08-03** (current edition read and published).
**The verdict is the opposite of the other entries in this section: this one was never a
granularity trap.**

* **IMPLAN / CARTO SALTILLO does not publish it.** 21 layers reviewed (boundaries, demography,
  public space, risk atlas, transport, heritage, mobility) — none cadastral. This rules out the
  route that would have been easiest, since that portal is already a source for this project.
* **The document exists and is municipal:** *«Tablas de Valores de Suelo y Construcción»*,
  Tesorería Municipal, on Saltillo's transparency portal (Article 28 §XIII), as PDF. The
  Congreso de Coahuila publishes an equivalent edition per year, which is where the value
  tables are attached to the approving decree.
* **Granularity: BY COLONIA / FRACCIONAMIENTO, by name.** Verified by extracting the text of
  the Congreso's Saltillo edition. The header reads *«TABLAS DE VALORES CATASTRALES POR
  COLONIAS Y FRACCIONAMIENTOS APLICABLE A LOS PREDIOS URBANOS DEL MUNICIPIO DE SALTILLO»*, with
  columns `COLONIA O FRACCIONAMIENTOS` and `TIPO DE TERRENO`. **This is the same unit the app
  already works in**, so no geometry, no spatial join and no new dependency is needed — the
  key is the colonia name the AGEB layer already carries.
* **The value is a two-step lookup**, both tables in the same document: colonia → a class
  (`POPULAR (1)`, `INTERES SOCIAL (2)`, `MEDIO ALTO`, `RESIDENCIAL 1a.`, `ZONA TIPICA`,
  `INDUSTRIAL (1)`…) → pesos per m². The class distribution over 660 rows is itself informative:
  `POPULAR (1)` 151, `INTERES SOCIAL (2)` 114, `POPULAR (2)` 112, `RESIDENCIAL 1a.` 66,
  `MEDIO BAJO` 63, `MEDIO MEDIO` 55, `MEDIO ALTO` 52, `INTERES SOCIAL (1)` 34,
  `INDUSTRIAL` 10, `ZONA TIPICA` 3.
* **It discriminates, which is exactly what CENAPRED and crime incidence failed to do.** In the
  edition read, the class values span **$149.50/m² (`POPULAR (1)`) to $1,685.51/m²
  (`RESIDENCIAL DE LUJO`) — an 11× spread across the city**. `ZONA CENTRO` is handled by a
  separate table with min/max ranges per terrain type rather than a single figure.
* **The name join was measured, not assumed.** Against the 226 Saltillo colonias the app
  publishes: **145 exact matches (64.2%)** after folding accents, case, punctuation and
  zero-padding (`5 DE MAYO` = `05 DE MAYO`). Of the 81 misses, **49 would match on token-subset**
  (word order, e.g. app `AMPLIACIÓN 26 DE MARZO` vs cadastre `26 DE MARZO II SECTOR AMPLIACION`)
  and **32 have no counterpart at all** — and those are dominated by developments that postdate
  the edition read (`HABITA`, `REAL ANKARA`, `ARBOREA`, `ANALCO II`). So 64% is a **floor
  measured on an old edition with naive matching**, not the achievable rate.
* **The current edition has now been read (2026-08-03).** Downloaded from the municipal
  transparency portal (13.96 MB, `raw_data/catastro/`, gitignored — over the 10 MB limit of the
  fetch tool, which is why an older edition was used first). Same document family and same
  two-table structure. **Fiscal year 2026 values, verbatim:**

  | Tipo de terreno | $/m² | | Tipo de terreno | $/m² |
  |---|---:|---|---|---:|
  | LOCALIDAD (SOLAR) | 60.20 | | MEDIO MEDIO | 1,021.73 |
  | POPULAR (1) | 263.18 | | MEDIO ALTO | 1,238.38 |
  | INDUSTRIAL (1) | 309.71 | | RESIDENCIAL 1a | 2,225.34 |
  | POPULAR (2) / INDUSTRIAL (2) | 464.45 | | RESIDENCIAL DE LUJO | 2,967.17 |
  | CAMPESTRE | 483.52 | | ZONA TIPICA | 557.12 |
  | INTERES SOCIAL (1) | 619.40 | | INTERES SOCIAL (2) | 712.05 |
  | MEDIO BAJO | 866.99 | | | |

  **880 colonia rows** (up from 660 in the older edition), plus a separate `FRACCIONAMIENTOS 2026`
  table for newly registered developments. `ZONA CENTRO` keeps its own min/max table and is
  **not** in the colonia list — which explains one of the unmatched names below.
* **Join on the current edition: 161 of 226 Saltillo colonias exact (71.2%)**, up from 64.2% on
  the older one — the gap was newer developments, as predicted. Of the 65 misses, **46 would
  match on token-subset**, so **207 of 226 (91.6%) are reachable**. The 19 with no counterpart at
  all are mostly not urban colonias in the first place: `ZONA CENTRO` (separate table),
  `UAAAN (BUENAVISTA)` (university campus), `EJIDO ANGOSTURA` (rural), `LADRILLERA`,
  `CENTRO METROPOLITANO`, `TOPOCHICO`.
* **Data-quality caveat for whoever implements it:** the class labels are not internally
  consistent in the source — `RESIDENCIAL 1a.` (107 rows) vs `RESIDENCIAL 1a` (3),
  `RESIDENCIAL LUJO` (29) vs `RESIDENCIAL DE LUJO` (1), `MEDIO MEDIO` (68) vs `MEDIA MEDIA` (2).
  They must be normalised before the class is looked up in the value table, or a handful of
  colonias will silently fall through.
* **Extraction needs no new dependency**, but it does need one trick per edition: the cell
  separator inside the content streams is the document's language tag, and it **changes between
  editions** — `es-ES` in the older one, `es-MX` in 2026. Splitting on `es-[A-Z]{2}` handles both.
  A stdlib `zlib` pass over the FlateDecode streams recovers everything; no OCR, no `pypdf`.
  Note that a fetch tool reporting "unreadable" is **not** evidence of a scan: it simply does not
  inflate compressed streams.
* **Honesty requirement if this is ever published, and it is not optional for this audience:**
  a cadastral value is a **tax base, not a market price**. In Mexico it is set deliberately
  below market value, and here it is a *class* assigned to a whole colonia, not an appraisal of
  a property. Presenting it as "what land is worth here" would mislead exactly the user the
  product is for. It should be labelled as the official cadastral reference value, with its
  edition year, and the two-step derivation (colonia → class → $/m²) stated in the detail card.
* **Status: ready to implement, pending one design decision.** The source is in hand and the
  join is measured; nothing external is blocking. What is not decided is whether the value enters
  the Investment Index as a component or stays an informational layer. Note that a *low* land
  value is genuinely ambiguous for an investor — cheap entry versus weak area — so unlike
  services (higher is better) and risk (higher is worse), it has no obvious sign, and picking one
  arbitrarily would bake an unstated thesis into the score.

### 3.6 AlphaEarth Foundations / Satellite Embedding — evaluated 2026-08-03, screening approved, nothing trained

User's idea (2026-08-03), after seeing an engineer combine AlphaEarth with ML to predict burned
areas near Acapulco. **No data was downloaded.** This entry is the decision document that task
asked for. Everything below was verified on 2026-08-03 against primary sources or measured
locally; none of it is from memory.

**What it is.** A geospatial embedding model from Google DeepMind. Its public output is the
*Satellite Embedding* dataset: **64 dimensions per 10 m pixel, one image per year**, covering
global land and shallow water. Each vector condenses a year of observations across Sentinel-2,
Landsat optical and thermal, radar, 3D surface measurements, elevation, climate, gravity fields
and descriptive text. The vectors are **unit-norm — points on a 64-dimensional sphere — so the
dot product is the cosine similarity**, and that is the intended comparison operation. Google
states the space is temporally consistent by design, so a stable place keeps a similar vector
across years and the angle between two years is the documented change-detection operator. The
documentation is explicit that **individual bands have no independent meaning**.
Years: 2017–2024 in the Earth Engine catalog, 2017–2025 on the public mirror.
Citation required: Brown, Kazmierski, Pasquarella et al. (2025), arXiv:2507.22291.

**The commercial question is answered, and the answer is the one that unblocks this.** The
dataset is **CC-BY 4.0** — commercial use is permitted with attribution, and the attribution
string is fixed: *"The AlphaEarth Foundations Satellite Embedding dataset is produced by Google
and Google DeepMind."* The concern on record was that a product aimed at investors would hit a
Google-terms wall. There is no such wall on the data. There *is* one on the platform: Earth
Engine separates a free noncommercial tier from a paid commercial account, and a company using
it operationally needs the latter. **That is a reason to not use Earth Engine, not a reason to
drop the dataset** — see access below.

**Access, and the route that matters.** Two exist. Earth Engine needs a Google account, project
registration and its own Python client, and drags the commercial-tier question along. The
alternative is a public mirror on Source Cooperative / AWS Open Data:
`s3://us-west-2.opendata.source.coop/tge-labs/aef/v1/annual/`, **anonymous, no AWS account**,
Cloud-Optimized GeoTIFFs organized by year and UTM zone, with a spatial index for finding the
tiles that intersect a bounding box. Saltillo is UTM zone **14N**. The mirror keeps this project
off Earth Engine's terms entirely and off a Google account.

**Local cost, measured rather than assumed.** Reading a COG needs `rasterio`. The precedent was
discouraging: `fiona` was skipped from this project because there is no GDAL wheel for Python
3.14 on Windows. **`rasterio` 1.5.0 is not blocked** — a `pip install --dry-run
--only-binary=:all: rasterio` on this venv's interpreter (3.14.6, AMD64) resolves cleanly to
wheels, pulling only `affine`, `click`, `cligj` and `pyparsing`. `numpy` 2.5.1 is already
installed. So the whole thing is **one dependency**, no GDAL build, no cloud SDK.

**Data volume, measured against this project's own extent.** The published AGEB layer spans
**49.8 × 37.6 km** (431 AGEBs, three municipios). At 10 m that is **18.72 M pixels**, and a
64-band `int8` array over it is **1.20 GB for a single year** — not "a small crop". One source
COG tile in zone 14N is **~3.2 GB**; the small STAC index is 4.99 MB (the full index parquet is
77.8 MB). The screening step below avoids all of this by reading a COG **overview** instead of
full resolution.

**The objection that decides the headline use case.** The embeddings are **annual**: they
summarize a full year's trajectory, and Google's own documentation frames them as year-long
patterns, not sub-annual events. **A pluvial flood that stands water for hours has no signal of
its own here.** So the honest reframing of "contrast the flood layer" is not *detect the July
2025 flood* — that is out of reach — but *do the colonias that flooded carry a distinguishable
land-cover and terrain signature?* That is a susceptibility proxy, and a weaker claim than the
task note assumed.

**And the label problem is worse than it looks.** The positives are the 16 colonias one
newspaper named. There are **no negatives**: a colonia that was not reported may simply not have
been reported. That is positive-unlabeled learning with ~16 positives at colonia granularity,
against 342 Saltillo AGEBs. Google's own published anchor for "few labels" is **150 samples per
class**. Pixel counts do not rescue this — the 10 m pixels inside one colonia are not
independent samples, and the unit in which this app publishes *every* number is the AGEB.

**The five candidate uses, re-ranked after the evidence:**

1. **Contrast the flood layer — weakened, not dead.** This is the open wound in §2.4, and it is
   still the use that would matter most. But it survives only in the reframed, weaker form
   above, and only if the screening below says the signature separates. Decision rule fixed
   *before* running: if it does not, this use is dropped and recorded here, like fire and
   insecurity were.
2. **Detect change since the 2020 Census — the strongest one, and it was not the headline.**
   Year-over-year angle is the documented operation, needs **no labels at all**, and yields a
   bounded, defensible claim: *this sector has changed a lot since the Census was taken*. It
   flags staleness without inventing a single Census figure. It survives precisely where the
   others do not, because it asks nothing of a training set.
3. **Fire / wildland-urban interface — still blocked, and by the same thing as in §3.3.** That
   entry deferred fire because the hazard is in the sierra where there are no AGEBs, not only
   because no source published a layer. AlphaEarth supplies a source; **it does not supply an
   analysis unit**. Fixing the source does not fix the geometry.
4. **Filling the gaps** (96 AGEBs with no cadastral row, 21 with no Census figures). Needs
   land-use labels this project does not have, and would be inventing a category where today
   there is an honest blank.
5. **Expansion to Monterrey / Torreón / Monclova.** The real strategic argument — every risk
   layer we publish is IMPLAN's and therefore Saltillo-only — but it is downstream of (2)
   working, not a reason on its own.

**What must be true if any of this ships, and it is not negotiable.** The premise of this whole
file is *verified official provenance*: every number the app publishes traces to a document with
a publisher and a cutoff date. **Model output is a different kind of claim.** If it enters, it
enters as a separate layer, labelled as this project's own estimate, with its method and its
error, **never merged into a field that cites a source, and never into the Investment Index** —
which has no slot for a term with no publisher to refer the reader to. The ethical precedent set
in §3.4 applies with more force, not less: a model that marks zones affects real people's
property, and *"our model predicts high risk here"* is a **stronger** assertion than citing an
atlas, because there is nobody to appeal to behind it.

**Approved next step — screening only, no training, not yet run:**

1. Read the STAC geoparquet index (4.99 MB) and select the 14N tiles intersecting the project
   bbox `-101.067, 25.263, -100.571, 25.607`.
2. Read a COG **overview** rather than full resolution. At ~160 m the extent is ~73 K pixels,
   about **4.7 MB instead of 1.20 GB** — enough to answer "do these look alike?" for roughly
   1/250th of the transfer. **Check before trusting it:** overview pixels are averaged
   embeddings, and a mean of unit vectors is not itself unit-norm, so renormalize and confirm
   against a full-resolution sample before drawing any conclusion. Values arrive as `int8` and
   need rescaling to the documented −1…1 range.
3. Aggregate to AGEB (mean pixel vector, renormalized): a 431 × 64 table, ~220 KB.
4. Answer two questions with cosine similarity alone, no model: **(a)** do zones we already know
   to be different separate — the GIS industrial sector, residential colonias, the sierra?
   **(b)** are the 16 flooded colonias closer to each other than to a random sample of the same
   size? If (a) fails, the pipeline is wrong. If (b) fails, use 1 dies cheaply.

**What NOT to do, so it does not have to be re-litigated:**

* **Do not train anything** before (b) answers.
* **Do not use Earth Engine.** The mirror avoids the account, the commercial tier and the
  platform terms, and keeps the stack at `pandas` + `geopandas` + one new wheel.
* **Do not add `aef-loader`.** It is purpose-built and tempting, but it pulls `asyncio`,
  `obstore`, `VirtualiZarr`, `odc-geobox` and `dask` into a project whose entire data stack is
  `pandas` and `geopandas`. `rasterio` alone does a windowed COG read over HTTPS.
* **Do not validate at pixel level and report at AGEB level.** That is how 18.72 M "samples"
  turn into a confidence nobody earned.
* **Do not let a model result reach the Investment Index**, or share a field with a cited figure.

---

## 4. Traceability of the published layers

For each file served to the browser, its origin:

| Layer in `data/` | Size | Derived from |
|---|---|---|
| `servicios_basicos.geojson` | ~627 KB | AGEB (§2.1) + Census 2020 (§2.2) |
| `indice_inversion.geojson` | ~649 KB | §2.1 + §2.2 + DENUE (§2.3) + flood risk (§2.4) |
| `riesgo_inundacion.geojson` | ~1.0 MB | IMPLAN flooding (§2.4) |
| `riesgo_deslizamientos.geojson` | ~164 KB | IMPLAN landslides (§2.5) |
| `riesgo_quimico.geojson` | ~1.28 MB | IMPLAN chemical-technological (§2.6) |
| `riesgo_inundacion.png` + `_meta.json` | ~174 KB | CONAGUA ANRI (§2.7) |
| `calles.json` | ~459 KB | AGEB block fronts, `fm` layer (§2.1) |
| `valor_catastral.json` | ~19 KB | Cadastral tables (§2.8), keyed by AGEB |

`calles.json` is not a map layer: it carries no geometry, it is fetched **lazily on the first
search** rather than on page load, and it exists to answer "which settlement is this street
in?". It is therefore outside the 5 MB budget SPEC §2 sets for the GeoJSON layers, whose
purpose is initial load time.

`valor_catastral.json` **is** a map layer, and the only one with no geometry file of its own.
The figures are published per colonia, so it ships as a lookup keyed by AGEB and borrows the
polygons the services layer already fetched. A third copy of the AGEB geometry would have cost
~640 KB against a budget already at 4.41 MB; as a lookup it costs 19 KB. It carries its source,
edition and the "tax base, not market price" warning in the file itself, so the caveat travels
with the data rather than living only in the frontend.

The risk layers carry provenance embedded in each feature's `FUENTE` and `FECHA` fields,
and the app shows it in the detail card on click, satisfying the project's traceability
requirement.

**Note on the risk card: it combines two sources.** The phenomenon and the intensity level
come from IMPLAN (§2.4, §2.5 and §2.6), but the colonia name and the municipality come from
INEGI's AGEBs (§2.1), locating the clicked point by point-in-polygon. The IMPLAN layers
carry no zone name: they are an intensity model and are dissolved by level. The colonia is
therefore an approximate location reference — the AGEB containing the point — not an IMPLAN
analysis unit: risk is modeled by zone, not by colonia, and a colonia can contain several
intensity levels.

The risk layers **drop the "Muy bajo" level**, which covers ~90-98% of the area and would
only bloat the file without adding signal. **The chemical layer additionally drops "Bajo"**
(see §2.6: there that level is 93% of the grid and, without trimming it, the layer would
exceed the 5 MB limit on its own). They are dissolved by intensity level — that is the
geometry feeding the Investment Index penalty — and on export are split back into their
individual zones (1,358 in flooding, 197 in landslides, 2,136 in the chemical one) so the
map can highlight one zone at a time instead of an entire level. The geometry is identical
either way; splitting only repeats the properties on each feature.

---

## 5. Pending

* **~~Ramos Arizpe and Arteaga~~ — DONE (2026-07-17).** Integrated: 431 AGEBs across 3
  municipalities (see §2.1). The Census and DENUE already covered all of Coahuila, so the
  services and investment indices computed themselves for the new municipalities (Ramos
  Arizpe mean INVERSION_INDEX 76.6, Arteaga 71.9; their RIESGO_INDEX is 0 because there is
  no IMPLAN risk layer outside Saltillo). Verified in the browser.
* **Coverage of the risk layers:** the IMPLAN layers are municipal (**Saltillo only**).
  Ramos Arizpe and Arteaga have AGEBs but **no** risk data, and the **visible-area-aware
  layer panel** already communicates this (it disables + explains those layers when
  navigating there). Still pending: check whether IMPLAN publishes atlases for those
  municipalities or whether another source is needed. **San Antonio de las Alazanas**
  (sierra, already with AGEBs) is the trigger for revisiting **forest-fire risk** (§3.3).
* **Forest-fire risk (Layer 2):** no source evaluated yet. Before implementing it, granular
  data for Arteaga / the sierra must be confirmed to exist.
* **Confirm with IMPLAN** the exact edition date of the risk layers if month-level precision
  ever matters (see the note in §2.5).
