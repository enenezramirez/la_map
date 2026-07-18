# Bitácora de Datos: GeoRiesgos Saltillo

Registro de procedencia de todos los conjuntos de datos usados en el proyecto, en
cumplimiento de **SPEC.md §1.2 (Legitimidad y Trazabilidad de los Datos)**. Como el
análisis se usa para decisiones inmobiliarias, cada capa debe poder rastrearse hasta su
fuente oficial, su fecha de corte y la fecha en que la descargamos.

**Cómo se llenó esta bitácora:** las fechas de publicación y los títulos oficiales se
tomaron de los metadatos que vienen dentro de cada paquete descargado (archivos
`metadatos/*.txt` de INEGI y `*.shp.xml` de los shapefiles), no de lo que recordábamos.
Las fechas de descarga provienen de la marca de tiempo de las carpetas en `raw_data/`.
Cuando un dato no se pudo verificar, se dice explícitamente en lugar de estimarlo.

**Última actualización:** 2026-07-16

---

## 1. Resumen

| # | Dataset | Editor | Corte / edición | Descarga | Estado |
|---|---------|--------|-----------------|----------|--------|
| 1 | Información vectorial de localidades amanzanadas y números exteriores 2023 | INEGI | 2023-12-15 | 2026-07-08 | En uso |
| 2 | Censo de Población y Vivienda 2020 (AGEB y manzana urbana, Coahuila) | INEGI | 2021-07-26 | 2026-07-08 | En uso |
| 3 | DENUE 05_2026 (Coahuila) | INEGI | 2026-05-20 | 2026-07-08 | En uso |
| 4 | Riesgo por inundaciones pluviales urbanas (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-15 | En uso |
| 5 | Riesgo por deslizamientos traslacionales (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-15 | En uso |
| 6 | Riesgo químico-tecnológico (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-17 | En uso |
| 7 | ANRI — Severidad por inundación, Tr = 100 años | CONAGUA | No publicada | 2026-07-16 | Respaldo |
| 8 | Riesgo por deslizamientos rotacionales (Atlas de Riesgos 2024) | IMPLAN Saltillo | 2024 | 2026-07-17 | Evaluado, no publicado |
| 9 | Indicadores Municipales PEV | CENAPRED | — | 2026-07-08 | Descartado |
| 10 | Susceptibilidad a inundaciones pluviales | IMPLAN Saltillo | 2024 | 2026-07-15 | Descartado |

---

## 2. Datasets en uso

### 2.1 INEGI — Información vectorial de localidades amanzanadas y números exteriores 2023

Aporta los polígonos de AGEB (la unidad territorial base de todo el análisis) y el nombre
de colonia de cada uno.

* **Título oficial:** *Información vectorial de localidades amanzanadas y números
  exteriores 2023. 050300001 (SALTILLO).*
* **Editor:** Instituto Nacional de Estadística y Geografía (INEGI).
* **Fechas (metadatos del producto):** creación 2023-10-02, revisión 2023-10-16,
  **publicación 2023-12-15**. Actualización anual.
* **Fecha de descarga:** 2026-07-08.
* **Ruta local:** `raw_data/marco_geoestadistico/saltillo_map_ageb/` (una carpeta por
  localidad: `050300001` Saltillo ciudad + 3 localidades rurales).
* **Colección:** *Información vectorial de localidades amanzanadas y números exteriores*.
  **Edición: 2023.** Cobertura temporal: 2011-01-01 a 2023-09-30.
* **Sitio de descarga:** Biblioteca digital de Mapas de INEGI
  (<https://www.inegi.org.mx/app/mapas/>), una ficha descargable por localidad.
* **Licencia:** Términos de Libre Uso de la Información del INEGI
  (<https://www.inegi.org.mx/inegi/terminos.html>).
* **Uso en el proyecto:** capa AGEB (`filtrar_agebs_por_municipio`) y nombre de colonia
  por AGEB, derivado de la capa de Frente de manzana (`fm`, campo `NOMASEN`) tomando el
  asentamiento más frecuente en cada AGEB (`cargar_nombres_colonias`).
* **Limitación conocida:** el AGEB es una unidad estadística y no coincide 1 a 1 con una
  colonia. El nombre es el asentamiento *dominante* entre los frentes del AGEB, no una
  frontera oficial de colonia: un AGEB puede abarcar varias.
* **Valores de relleno en `NOMASEN`:** el campo usa **`ND`** (no disponible; su `TIPOASEN`
  también dice `ND`, 363 frentes) y **`NINGUNO`** (frente sin asentamiento asignado, 141
  frentes) como marcadores, no como nombres. Hay que descartarlos antes de calcular el
  asentamiento dominante: un AGEB con 5 frentes `NINGUNO` y 4 con nombre real acabaría
  llamándose "NINGUNO". Ver `VALORES_SIN_ASENTAMIENTO` en `scripts/process_data.py`.
  **Cuidado al ampliar la lista:** no todo valor corto o extraño es relleno — `GIS` es un
  nombre real (Sector GIS, por Grupo Industrial Saltillo).
* **Cobertura actual (2026-07-17):** 3 municipios, **431 AGEBs** — Saltillo (342), Ramos
  Arizpe (61) y Arteaga (28), la Zona Metropolitana que pide `SPEC.md §1.1`. Descargados
  por municipio (paquetes `05004`/`05027`, producto `vla_ne_mg_2022`) y reorganizados a
  `arteaga_map_ageb/` y `ramos_arizpe_map_ageb/` (mismo patrón que `saltillo_map_ageb/`).
  Localidades con capa de AGEB: `050040001` Arteaga cabecera, `050040107` San Antonio de
  las Alazanas (sierra) y `050270001` Ramos Arizpe ciudad; el resto de localidades de cada
  paquete son rurales sin AGEB (se omiten con gracia). 428/431 AGEBs con datos de censo (3
  sin match, probablemente no residenciales); 0 con `SIN_COLONIA`.

> **Corrección de atribución.** Este producto se venía citando como *"Marco
> Geoestadístico"*. **No lo es**, aunque la confusión es entendible: INEGI lo clasifica
> bajo el **tema** "Marco Geoestadístico" y se descarga del mismo portal. Pero es un
> producto distinto, que *usa* el Marco Geoestadístico (edición diciembre 2022) como capa
> base, junto con GEODOM 2010-2016, la Cartografía Urbana y Rural 2017-2023, los Censos
> Económicos 2019 y el CPV 2020. Cítese siempre con el título y la edición de este
> apartado. Corregido en `README.md`, `CLAUDE.md`, `SPEC.md`, `task.md` y
> `scripts/process_data.py`. La carpeta `raw_data/marco_geoestadistico/` conserva el
> nombre viejo a propósito: renombrarla rompería copias locales de datos no versionados
> sin ganar nada.

### 2.2 INEGI — Censo de Población y Vivienda 2020 (AGEB y manzana urbana)

* **Título oficial:** *Principales resultados por AGEB y manzana urbana del Censo de
  Población y Vivienda 2020. Datos oportunos* — entidad Coahuila de Zaragoza.
* **Identificador:** `MEX-INEGI.ESD2.01-CPV-2020`.
* **Editor:** INEGI. Información de Interés Nacional (SNIEG).
* **Fecha de corte del censo:** 2020. **Última modificación del archivo: 2021-07-26**
  (se agregaron AGEBs y manzanas de localidades urbanas de menos de 2,500 habitantes).
* **Fecha de descarga:** 2026-07-08.
* **Ruta local:** `raw_data/ageb_mza_urbana_05_cpv2020_csv/.../conjunto_de_datos_ageb_urbana_05_cpv2020.csv`.
* **Licencia:** Términos de Libre Uso de la Información del INEGI.
* **Uso en el proyecto:** cobertura de servicios básicos por AGEB — `VPH_C_ELEC`
  (electricidad), `VPH_AGUADV` (agua), `VPH_DRENAJ` (drenaje) y `VPH_INTER` (internet),
  todas sobre `TVIVHAB`, más el compuesto `SERVICIOS_INDEX`.
* **Limitación conocida:** al estar agregado por AGEB, el Censo **no permite** calcular el
  porcentaje de viviendas con *todos* los servicios simultáneamente (eso requeriría
  microdatos). `SERVICIOS_INDEX` es el promedio de los cuatro, una aproximación.

### 2.3 INEGI — DENUE 05_2026 (Coahuila)

* **Título oficial:** *Directorio Estadístico Nacional de Unidades Económicas (DENUE)
  05_2026.*
* **Identificador:** `MEX-INEGI.EEC2.05-DENUE-2026`.
* **Editor:** INEGI.
* **Fecha de corte / modificación: 2026-05-20.** Actualización anual.
* **Fecha de descarga:** 2026-07-08.
* **Sitio de descarga:** <https://www.inegi.org.mx/app/descarga/?ti=6>.
* **Ruta local:** `raw_data/denue_05_csv/conjunto_de_datos/denue_inegi_05_.csv`.
* **Licencia:** Términos de Libre Uso de la Información del INEGI.
* **Uso en el proyecto:** componente "Comercios" del Índice de Inversión — escuelas
  (SCIAN 61), salud (SCIAN 62) y supermercados (por nombre de giro, ya que no tienen
  sector SCIAN propio), medidos como cercanía del centroide del AGEB al establecimiento
  más próximo de cada categoría.

### 2.4 IMPLAN Saltillo — Riesgo por inundaciones pluviales urbanas (Atlas de Riesgos 2024)

**Fuente primaria de riesgo hidrometeorológico** (SPEC Capa 1).

* **Fuente oficial:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Sitio de descarga:** <https://implansaltillo.mx/perfil/> (portal CARTO SALTILLO;
  ofrece las capas en SHP, KML y PDF).
* **Fecha de corte:** **2024**, según la etiqueta del portal ("Atlas de Riesgos 2024").
* **Fecha de descarga:** 2026-07-15.
* **Ruta local:** `raw_data/Riesgo_por_inundaciones_pluviales3/`.
* **Formato:** shapefile, 12,679 registros, EPSG:6372 (MEXICO_ITRF_2008_LCC).
* **Campos:** `Titulo`, `Intensid_1` (nivel de intensidad), `Detall`, `Fenom`.
* **Título interno del shapefile:** `R050300001_R_INUNDACION_PLUVIAL`.
* **Licencia / condiciones:** el portal ofrece acceso público a la información y deslinda
  al IMPLAN de la responsabilidad por el mal uso de los datos.
* **Uso en el proyecto:** capa `data/riesgo_inundacion.geojson` y penalización por riesgo
  del Índice de Inversión (`RIESGO_INDEX`, vía overlay AGEB↔riesgo en EPSG:6372).

### 2.5 IMPLAN Saltillo — Riesgo por deslizamientos traslacionales (Atlas de Riesgos 2024)

**Fuente primaria de riesgo geológico** (SPEC Capa 4).

* **Fuente oficial:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Crédito de autoría (metadatos del shapefile):** **Instituto de Geografía de la UNAM**
  (`idCredit: "IGg. UNAM"`). El shapefile de inundación no trae crédito.
* **Sitio de descarga:** <https://implansaltillo.mx/perfil/>.
* **Fecha de corte:** 2024 (etiqueta del portal).
* **Fecha de descarga:** 2026-07-15.
* **Ruta local:** `raw_data/Riesgo_por_Deslizamientos_traslacionales2/`.
* **Formato:** shapefile, 12,679 registros, EPSG:6372.
* **Campos:** `Titulo`, `Intensid_1`, `Detalle`, `Fenome`.
* **Título interno del shapefile:** `R05030_RIESGO_PRM_DESLIZAMIENTOS_TRASLACIONALES_TR2_MZ`.
* **Uso en el proyecto:** capa `data/riesgo_deslizamientos.geojson`.

> **Sobre las fechas de las dos capas IMPLAN.** Los archivos declaran internamente
> modificación 2025-02-27 y creación 2025-04-01/02, posteriores a la etiqueta "2024" del
> portal. Se interpretan como fechas de exportación del archivo, no de la edición del
> Atlas, por lo que **la fecha de corte publicada en la app sigue siendo 2024**, que es
> como el editor nombra el producto (`IMPLAN_FECHA_CORTE` en `scripts/process_data.py`).
> Vale confirmarlo con el IMPLAN si alguna vez importa la precisión al mes.

### 2.6 IMPLAN Saltillo — Riesgo químico-tecnológico (Atlas de Riesgos 2024)

**Fuente primaria de riesgo antropogénico**, muy relevante en el corredor industrial
Saltillo–Ramos Arizpe (GM, Stellantis, GIS).

* **Fuente oficial:** IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024.
* **Sitio de descarga:** <https://implansaltillo.mx/perfil/>.
* **Fecha de corte:** 2024 (etiqueta del portal).
* **Fecha de descarga:** 2026-07-17.
* **Ruta local:** `raw_data/Riesgo_Quimico_tecnologico/`.
* **Formato:** shapefile de **polígonos** (no puntos), 12,679 registros, EPSG:6372 — la
  misma malla que inundación y deslizamientos.
* **Campos:** `Titulo` ("Riesgo Químico-Tecnológico"), `Intensid_1` (Muy Bajo→Alto; sin
  "Muy alto"), `Detalle` ("Riesgo por almacenamiento de sustancias químicas peligrosas"),
  `Fenome` ("Químico-Tecnológico").
* **Uso en el proyecto:** capa `data/riesgo_quimico.geojson`. **Solo informativa** (no
  penaliza el Índice de Inversión; igual que deslizamientos, solo la inundación penaliza).
* **Umbral propio (Medio+Alto).** A diferencia de las otras capas —que solo descartan "Muy
  bajo"—, esta descarta también **"Bajo"**: ahí ese nivel cubre 9,644 de 12,679 celdas (el
  93% de la malla), es el fondo del modelo sin valor discriminante y, conservándolo, la
  capa pesaría **6.9 MB** (rebasa sola el límite de 5 MB de SPEC §2). Con Medio (1,937) +
  Alto (212) queda en **1.28 MB / 2,136 zonas** mostrando solo la exposición genuina. El
  umbral vive en `NIVELES_ELEVADOS_QUIMICO` (`scripts/process_data.py`), pasado a
  `preparar_capa_riesgo(niveles=...)`.

### 2.7 CONAGUA — ANRI, Severidad por inundación (Tr = 100 años) *(respaldo)*

Se conserva como fuente alternativa; **IMPLAN es la primaria** por ser local, vectorial y
más reciente. Este dataset es raster y de menor granularidad.

* **Fuente oficial:** CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI), Región
  Noreste. Capa "Severidad, periodo de retorno 100 años" (Saltillo, Coahuila).
* **Servicio:** <https://rmgir.proyectomesoamerica.org/server/rest/services/ANRI/RegionNoreste_ANRI/MapServer/142>
  (ArcGIS REST, capa 142).
* **Fecha de descarga / consulta:** 2026-07-15; re-descargado el 2026-07-16 y el raster
  volvió byte-idéntico, así que la fuente no ha cambiado entre ambas fechas. El servicio
  no publica fecha de corte. `fecha_descarga` en `riesgo_inundacion_meta.json` se
  reescribe con la fecha del día cada vez que se corre el pipeline.
* **Variable:** severidad (índice compuesto de tirante y velocidad); clases alta, media y baja.
* **Ruta local:** `data/riesgo_inundacion.png` + `data/riesgo_inundacion_meta.json`
  (PNG georreferenciado para usarse como `imageOverlay` en Leaflet).
* **Generado por:** `descargar_raster_inundacion()` en `scripts/process_data.py`.
* **Nota oficial:** aproximación por modelación hidráulica; no sustituye un estudio de sitio.

---

## 3. Datasets descartados y fuentes evaluadas

Se documentan para no volver a evaluarlos desde cero.

### 3.1 CENAPRED — Indicadores Municipales PEV

* **Ruta local:** `raw_data/cenapred_indicadores_municipales/` (2,469 registros, todo México).
* **Fecha de descarga:** 2026-07-08.
* **Motivo del descarte:** **resolución municipal**. Sus campos de peligro
  (`GP_INUNDAC`, `SUSCEPLAD`, `GP_SISMICO`…) dan un solo valor para todo el municipio de
  Saltillo, inservible para distinguir riesgo entre colonias, que es justo el propósito de
  la app. Sustituido por las capas vectoriales del IMPLAN.

### 3.2 IMPLAN — Susceptibilidad a inundaciones pluviales

* **Ruta local:** `raw_data/SUSCEPTIBILIDAD_INUNDACIONES_PLUVIALES/`
  (`S05030_SUSCEPTIBILIDAD_INUNDACIONES_PLUVIALES`).
* **Fecha de descarga:** 2026-07-15.
* **Motivo del descarte:** mide **susceptibilidad** (predisposición del terreno), no
  **riesgo** (que ya incorpora exposición y vulnerabilidad). La capa de riesgo del mismo
  Atlas es la adecuada para el propósito de la app y las haría redundantes.

### 3.2b IMPLAN — Riesgo por deslizamientos rotacionales (Atlas 2024) — descargado, no publicado

* **Ruta local:** `raw_data/Riesgo_por_Deslizamientos_rotacionales3/` (12,679 polígonos,
  EPSG:6372). **Fecha de descarga:** 2026-07-17. Se conserva por si se reconsidera.
* **Motivo de no publicarla:** **valor añadido marginal**. Es la capa hermana de la
  traslacional que sí usamos (§2.5), pero su nivel de intensidad máximo es apenas "Medio"
  (75 celdas de 12,679); el resto es "Bajo"/"Muy bajo" de fondo. Con el tratamiento estándar
  pesaría 2.3 MB de mayoría "bajo", y quedarse solo con "Medio" son 75 celdas (~49 KB) de
  señal muy débil. **No cambia una decisión de inversión**, que es la vara para incluir una
  capa. Verificado a nivel de celda contra la traslacional (misma malla): de sus 3,882
  celdas elevadas solo 76 se solapan con la traslacional, y sus 75 celdas "Medio" caen todas
  donde la traslacional ve "Muy bajo" — o sea, aporta terreno distinto, pero de intensidad
  baja. **No se fusiona con la traslacional**: son mecanismos de falla distintos (plano vs.
  superficie cóncava) con escalas de intensidad no necesariamente comparables; mezclarlas
  crearía una capa derivada sin fuente propia y rompería la trazabilidad de SPEC §1.2.
* **Reactivación:** si en el futuro se busca completitud del riesgo geológico, se agrega como
  **capa aparte** (nunca fusionada), preferentemente solo su nivel "Medio".

---

### 3.3 Riesgo por incendios forestales (SPEC Capa 2) — evaluado y aplazado

**No se descargó ningún dataset.** La capa se evaluó el 2026-07-16 y se decidió no
implementarla mientras el alcance sea Saltillo urbano. No es un descarte definitivo:
tiene criterio de reactivación.

* **Fuentes contempladas:** CONABIO/CONAFOR, IMPLAN, CENAPRED.
* **Motivos del aplazamiento:**
  1. **El IMPLAN no publica una capa de incendio.** Su Atlas de Riesgos 2024 (CARTO
     SALTILLO) mapea 7 capas —deslizamientos rotacionales y traslacionales, inundación
     pluvial urbana, susceptibilidad a inundación, almacenamiento de sustancias químicas,
     vulnerabilidad socio-organizativa y sanitario-ecológica— y ninguna es de incendio.
     El instituto de planeación del municipio, al cartografiar los riesgos de su propio
     territorio, no lo consideró relevante. Es la evidencia más fuerte en contra.
  2. **No hay unidad de análisis donde está el peligro.** El AGEB (§2.1) es urbano y hoy
     solo cubre Saltillo. El peligro de incendio está en la sierra y en Arteaga, donde no
     hay AGEBs: la capa pintaría territorio sobre el que la app no analiza nada. Compárese
     con las capas de riesgo actuales, que caen 100% dentro de la cobertura de AGEBs
     (1095/1095 y 195/195 puntos representativos verificados).
  3. **No discriminaría en el Índice de Inversión.** La penalización se calcula por
     intersección de área con cada AGEB; si el peligro apenas roza la mancha urbana, el
     resultado sería ≈0 para casi todos los sectores. Una variable que no distingue entre
     zonas no aporta al scoring y sí cuesta archivo, UI y mantenimiento.
  4. **La única fuente a mano es municipal.** El campo `GP_IF` de CENAPRED (§3.1) da un
     valor único para todo Saltillo: la misma falta de granularidad que ya descartó ese
     dataset.
* **Criterio de reactivación:** implementar cuando existan los AGEBs de **Arteaga**
  (`SPEC.md §1.1`). Ahí el riesgo es real —interfaz urbano-forestal en Los Lirios, San
  Antonio de las Alazanas y la Sierra de Zapalinamé— y habría sectores que analizar. En
  ese momento hay que volver a buscar fuente (CONAFOR/CONABIO, o el atlas de riesgos de
  Arteaga si existe), ya que el del IMPLAN de Saltillo no cubre ese municipio.

### 3.4 Inseguridad / incidencia delictiva — investigada y aplazada

Idea del usuario: muy relevante para una decisión inmobiliaria (pesa más que un 2º tipo de
deslizamiento). Se investigó a fondo el **2026-07-17** y se aplazó por **falta de dato con
granularidad útil**. No es descarte definitivo: tiene criterio de reactivación.

* **No se descargó ningún dataset.** El problema es de disponibilidad, no de esfuerzo.
* **Fuentes revisadas y su granularidad:**
  * **SESNSP** (nacional, oficial) — solo **estatal y municipal**; nada por debajo de
    municipio fuera de CDMX. Un valor único para todo Saltillo.
  * **Fiscalía General de Coahuila / Comisaría de Seguridad de Saltillo** — no publican
    dataset de incidencia por colonia. La Comisaría solo ofrece apps de **reporte
    ciudadano** (Saltillo Seguro, bot de WhatsApp) y encuestas de **percepción**.
  * **Observatorios** (ONC `delitosmexico`, Semáforo Delictivo Coahuila, RID del Consejo
    Cívico) — todos municipales.
  * **`mapa.ocl.org.mx`** — es el Observatorio Ciudadano de **León, Guanajuato** (dato por
    colonia con descarga .xlsx), **no** Coahuila. Prueba que el modelo por colonia existe
    en otras ciudades, pero no cubre Saltillo.
  * **HoyoDeCrimen** — georreferenciado por colonia pero **exclusivo de CDMX**.
  * **El Crimen (`elcri.men`), `lapanquecita/incidencia-delictiva` (GitHub)** — la mejor
    herramienta comunitaria; se alimenta del SESNSP, o sea **municipal**.
* **Motivo del aplazamiento:** misma **trampa de granularidad** que descartó a CENAPRED
  (§3.1). Un valor municipal único no discrimina entre colonias → peso muerto en el índice.
  La razón es estructural: el SESNSP no publica sub-municipal fuera de CDMX, por eso ningún
  proyecto comunitario lo ha resuelto para Saltillo.
* **Consideración ética (para cuando se reactive):** los datos de delito están sesgados por
  tasa de denuncia y un choropleth de "colonias peligrosas" en una app de scoring
  inmobiliario afecta el valor de propiedades de gente real y puede volverse profecía
  autocumplida. Si se implementa, debe ser con fuente oficial verificada, el sesgo
  declarado en la ficha, y decidiendo explícitamente si entra al índice o queda informativa.
* **Criterio de reactivación:** la única vía viable es la **macrozona del IMPLAN** — 12
  polígonos que agrupan AGEBs (definidos desde ~2017); la Comisaría analiza la inseguridad
  por macrozona ("Oriente" es la más insegura). Integraría limpio (misma fuente IMPLAN,
  base AGEB), pero **hoy no es dato abierto**: requeriría una gestión institucional ante el
  IMPLAN o la Comisaría (solicitud de transparencia / informe municipal con cifras por
  macrozona), no búsqueda web.

---

## 4. Trazabilidad de las capas publicadas

De cada archivo servido al navegador, su origen:

| Capa en `data/` | Tamaño | Derivada de |
|---|---|---|
| `servicios_basicos.geojson` | ~627 KB | AGEB (§2.1) + Censo 2020 (§2.2) |
| `indice_inversion.geojson` | ~649 KB | §2.1 + §2.2 + DENUE (§2.3) + riesgo de inundación (§2.4) |
| `riesgo_inundacion.geojson` | ~1.0 MB | IMPLAN inundación (§2.4) |
| `riesgo_deslizamientos.geojson` | ~164 KB | IMPLAN deslizamientos (§2.5) |
| `riesgo_quimico.geojson` | ~1.28 MB | IMPLAN químico-tecnológico (§2.6) |
| `riesgo_inundacion.png` + `_meta.json` | ~174 KB | CONAGUA ANRI (§2.7) |

Las capas de riesgo llevan la procedencia embebida en los campos `FUENTE` y `FECHA` de
cada feature, y la app la muestra en la ficha de detalle al hacer clic (SPEC §1.2).

**Ojo con la ficha de riesgo: combina dos fuentes.** El fenómeno y el nivel de intensidad
vienen del IMPLAN (§2.4, §2.5 y §2.6), pero el nombre de colonia y el municipio vienen de los
AGEB de INEGI (§2.1), ubicando el punto clicado por point-in-polygon. Las capas del
IMPLAN no traen nombre de zona: son un modelo de intensidad y se disuelven por nivel. La
colonia es, por tanto, una referencia de ubicación aproximada —el AGEB que contiene el
punto—, no una unidad de análisis del IMPLAN: el riesgo se modela por zona, no por
colonia, y una colonia puede contener varios niveles de intensidad.

Las capas de riesgo **descartan el nivel "Muy bajo"**, que cubre el ~90-98% del área y
solo agrandaría el archivo sin aportar señal. **La capa química descarta además "Bajo"**
(ver §2.6: ahí ese nivel es el 93% de la malla y sin recortarlo la capa rebasaría sola el
límite de 5 MB). Se disuelven por nivel de intensidad —esa es la geometría que alimenta la
penalización del Índice de Inversión— y al exportarlas se separan en sus zonas individuales
(1,358 en inundación, 197 en deslizamientos, 2,136 en la química) para que el mapa pueda
resaltar una zona a la vez en vez de todo un nivel. La geometría es idéntica en ambos
casos; separar solo repite las propiedades en cada feature.

---

## 5. Pendientes

* **~~Ramos Arizpe y Arteaga~~ — HECHO (2026-07-17).** Integrados: 431 AGEBs en 3
  municipios (ver §2.1). El Censo y el DENUE ya cubrían todo Coahuila, así que los índices
  de servicios e inversión se calcularon solos para los nuevos municipios (Ramos Arizpe
  INVERSION_INDEX media 76.6, Arteaga 71.9; su RIESGO_INDEX es 0 porque no hay capa de
  riesgo IMPLAN fuera de Saltillo). Verificado en navegador.
* **Cobertura de las capas de riesgo:** las capas del IMPLAN son municipales (**solo
  Saltillo**). Ramos Arizpe y Arteaga tienen AGEBs pero **no** datos de riesgo, y eso ya lo
  comunica el **panel sensible a la zona visible** (deshabilita+explica esas capas al
  navegar allá; ver `task.md`). Pendiente aún: verificar si el IMPLAN publica atlas de esos
  municipios o si hace falta otra fuente. **San Antonio de las Alazanas** (sierra, ya con
  AGEBs) es el disparador para retomar el **riesgo forestal** (§3.3).
* **Riesgo forestal (SPEC Capa 2):** sin fuente evaluada todavía. Antes de implementarla
  hay que verificar que existan datos granulares para Arteaga / la Sierra.
* **Confirmar con el IMPLAN** la fecha exacta de edición de las capas de riesgo si llega a
  importar la precisión al mes (ver nota en §2.5).
