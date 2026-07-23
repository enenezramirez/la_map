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
* **Use in the project:** AGEB layer (`filtrar_agebs_por_municipio`) and colonia name
  per AGEB, derived from the block-front layer (`fm`, field `NOMASEN`) by taking the most
  frequent settlement in each AGEB (`cargar_nombres_colonias`).
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
