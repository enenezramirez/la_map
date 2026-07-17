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
| 6 | ANRI — Severidad por inundación, Tr = 100 años | CONAGUA | No publicada | 2026-07-16 | Respaldo |
| 7 | Indicadores Municipales PEV | CENAPRED | — | 2026-07-08 | Descartado |
| 8 | Susceptibilidad a inundaciones pluviales | IMPLAN Saltillo | 2024 | 2026-07-15 | Descartado |

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
* **Cobertura actual:** solo municipio de Saltillo (342 AGEBs). Faltan Ramos Arizpe y
  Arteaga, contemplados en `SPEC.md §1.1`.

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

### 2.6 CONAGUA — ANRI, Severidad por inundación (Tr = 100 años) *(respaldo)*

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

## 3. Datasets descargados y descartados

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

---

## 4. Trazabilidad de las capas publicadas

De cada archivo servido al navegador, su origen:

| Capa en `data/` | Tamaño | Derivada de |
|---|---|---|
| `servicios_basicos.geojson` | ~488 KB | AGEB (§2.1) + Censo 2020 (§2.2) |
| `indice_inversion.geojson` | ~506 KB | §2.1 + §2.2 + DENUE (§2.3) + riesgo de inundación (§2.4) |
| `riesgo_inundacion.geojson` | ~1.0 MB | IMPLAN inundación (§2.4) |
| `riesgo_deslizamientos.geojson` | ~164 KB | IMPLAN deslizamientos (§2.5) |
| `riesgo_inundacion.png` + `_meta.json` | ~174 KB | CONAGUA ANRI (§2.6) |

Las capas de riesgo llevan la procedencia embebida en los campos `FUENTE` y `FECHA` de
cada feature, y la app la muestra en la ficha de detalle al hacer clic (SPEC §1.2).

**Ojo con la ficha de riesgo: combina dos fuentes.** El fenómeno y el nivel de intensidad
vienen del IMPLAN (§2.4 y §2.5), pero el nombre de colonia y el municipio vienen de los
AGEB de INEGI (§2.1), ubicando el punto clicado por point-in-polygon. Las capas del
IMPLAN no traen nombre de zona: son un modelo de intensidad y se disuelven por nivel. La
colonia es, por tanto, una referencia de ubicación aproximada —el AGEB que contiene el
punto—, no una unidad de análisis del IMPLAN: el riesgo se modela por zona, no por
colonia, y una colonia puede contener varios niveles de intensidad.

Las capas de riesgo **descartan el nivel "Muy bajo"**, que cubre el ~90-98% del área y
solo agrandaría el archivo sin aportar señal. Se disuelven por nivel de intensidad —esa
es la geometría que alimenta la penalización del Índice de Inversión— y al exportarlas se
separan en sus zonas individuales (1,358 en inundación, 197 en deslizamientos) para que
el mapa pueda resaltar una zona a la vez en vez de todo un nivel. La geometría es idéntica
en ambos casos; separar solo repite las propiedades en cada feature.

---

## 5. Pendientes

* **Ramos Arizpe y Arteaga:** falta descargar sus AGEBs (§2.1) para cubrir la Zona
  Metropolitana completa que pide `SPEC.md §1.1`.
* **Cobertura de las capas de riesgo:** las capas del IMPLAN son municipales (Saltillo).
  Al sumar Ramos Arizpe y Arteaga habrá que verificar si el IMPLAN publica sus atlas o si
  hace falta otra fuente para esos municipios.
* **Riesgo forestal (SPEC Capa 2):** sin fuente evaluada todavía. Antes de implementarla
  hay que verificar que existan datos granulares para Arteaga / la Sierra.
* **Confirmar con el IMPLAN** la fecha exacta de edición de las capas de riesgo si llega a
  importar la precisión al mes (ver nota en §2.5).
