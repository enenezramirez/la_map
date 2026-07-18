# Especificación Técnica: GeoRiesgos Saltillo

Este documento sirve como la especificación del sistema (Single Source of Truth) para el desarrollo de la aplicación.

---

## 1. Requerimientos Funcionales

1. **Mapa Base Interactivo:**
   - Mapa centrado en la Zona Metropolitana de Saltillo (Saltillo, Ramos Arizpe y Arteaga, Coahuila).
   - Base de mapa estética en tonos oscuros o claros limpios (por ejemplo, CartoDB Positron o Stadia Maps).
2. **Visualización de Capas (Layers):**
   - **Capa 1: Riesgos de Inundación (IMPLAN CARTO Saltillo, Atlas 2024):** Polígonos de zonas de riesgo por inundación pluvial urbana, coloreados semafóricamente por nivel de intensidad. Respaldo: ANRI de CONAGUA (raster de severidad). *El dataset municipal de CENAPRED se descartó por falta de granularidad.*
   - **Capa 2: Riesgo Forestal — APLAZADA (no se implementa mientras el alcance sea solo Saltillo urbano).** Áreas con peligro de incendios, especialmente en las zonas boscosas de Arteaga. *Evaluada y aplazada el 2026-07-16; ver la justificación completa en `DATOS.md` §3.3.* **Criterio de reactivación:** implementar cuando existan los AGEBs de Arteaga (`SPEC.md §1.1`), no antes. El resumen del porqué: el peligro está en la sierra, donde hoy no hay AGEBs —la unidad de análisis de toda la app— y el IMPLAN no publica una capa de incendio en su Atlas de Riesgos 2024.
   - **Capa 3: Cobertura de Servicios Básicos (INEGI, Censo de Población y Vivienda 2020):** Cobertura de agua, luz, drenaje e internet por sector, y un índice compuesto que las promedia. *Nota: el Censo agregado por AGEB no permite calcular el porcentaje de viviendas que tienen los cuatro servicios simultáneamente (requeriría microdatos); el promedio es la aproximación adoptada.*
   - **Capa 4: Riesgos Geológicos y Deslizamientos (IMPLAN CARTO Saltillo, Atlas 2024):** Zonas de riesgo por remoción de masa en laderas (deslizamientos traslacionales), coloreadas por nivel de intensidad.
3. **Índice de Inversión Inmobiliaria:**
   - Una capa combinada (Weighted Overlay) calculada en Python que sume los servicios básicos, penalice las zonas de riesgo y valore la cercanía a infraestructura. *Estado: hoy la penalización usa únicamente la exposición a inundación. Los incendios quedan fuera mientras la Capa 2 esté aplazada. Antes de sumar más riesgos a la penalización hay que decidir cómo se combinan entre sí, no solo apilarlos.*
4. **Panel de Control (UI/UX):**
   - Menú lateral responsivo con efecto glassmorphism.
   - Interruptores para capas e información emergente (tooltip/sidebar) al hacer clic en un sector.

### 1.1 Alcance Geográfico y Expansión Futura
* **Fase Inicial:** Saltillo, Ramos Arizpe y Arteaga (Zona Metropolitana de Saltillo).
* **Fase de Expansión:** Monterrey (Nuevo León), Torreón (Coahuila) y Monclova (Coahuila). La arquitectura debe ser modular para permitir añadir nuevas ciudades de forma sencilla reemplazando o sumando archivos GeoJSON independientes.

### 1.2 Legitimidad y Trazabilidad de los Datos
Dado que la precisión es crítica para la toma de decisiones inmobiliarias, la aplicación debe garantizar la procedencia de la información:
* **Bitácora de Datos:** `DATOS.md` es el registro único de procedencia del proyecto: fuente oficial, editor, fecha de corte, fecha de descarga, licencia y uso de cada dataset, incluidos los descartados y su motivo. Debe actualizarse al agregar, cambiar o descartar cualquier fuente, y sus fechas deben verificarse contra los metadatos internos de cada paquete, no de memoria.
* **Metadatos Obligatorios:** Cada capa debe documentar estrictamente en su código/GeoJSON la **Fuente Oficial** y la **Fecha de Descarga/Actualización** (ej. *IMPLAN CARTO Saltillo, Atlas de Riesgos 2024*).
* **UI Informativa:** Cuando el usuario haga clic en cualquier sector del mapa para ver los detalles, el panel de información debe mostrar visiblemente el origen y la fecha de corte de los datos de riesgo y servicios que está visualizando.

---

## 2. Arquitectura de Datos y Backend (Python)

El procesamiento de datos se ejecutará localmente y fuera de línea con Python.

### Unidad Territorial Base:
El "sector" de todo el análisis es el **AGEB** (Área Geoestadística Básica). Sus polígonos y el nombre de colonia asociado provienen de **INEGI — *Información vectorial de localidades amanzanadas y números exteriores 2023*** (publicado 2023-12-15). Este producto **no es** el Marco Geoestadístico: solo lo utiliza (edición diciembre 2022) como capa base. Toda cita a esta fuente debe usar su título oficial — ver `DATOS.md` §2.1.

### Herramientas de Datos:
- `pandas` y `geopandas` para el manejo de dataframes espaciales.
- `shapely` para operaciones geométricas (ej. validar si una colonia intersecta una zona de inundación).
- `pyogrio` (motor I/O rápido y por defecto en GeoPandas 1.x) y `pyproj` para conversión de sistemas de coordenadas (EPSG:4326 a nivel global).

### Formato de Salida:
- Los datos procesados se exportarán a archivos en la carpeta `data/` en formato GeoJSON (`.geojson`).
- Se debe procurar la simplificación de geometrías (usando el método `.simplify()` de GeoPandas) para mantener los archivos GeoJSON ligeros (< 5MB en total) para su rápida carga en el navegador.

---

## 3. Arquitectura Frontend (HTML/CSS/JS)

La interfaz se servirá de forma estática, facilitando el despliegue gratuito.

### Librerías Externas (Vía CDN):
- **Leaflet.js** (Core del mapa):
  - CSS: `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css`
  - JS: `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`
- **Fuentes:** Google Fonts (Inter).

### Estructura de Archivos:
- `index.html` - Estructura HTML y lógica JS para cargar el mapa e interactuar con los GeoJSON locales.
- `styles.css` - Estilos CSS con variables modernas, sombras suaves y diseño responsivo para móviles y escritorio.

---

## 4. Algoritmo del Índice de Inversión (Lógica del Scoring)

El índice se calculará a nivel de sector o colonia utilizando variables normalizadas entre `0` y `1`:

$$Puntaje = (Servicios \times W_{serv}) + (Comercios \times W_{com}) - (Riesgo \times W_{riesg})$$

Donde los pesos sugeridos son:
- $W_{serv} = 0.4$ (Drenaje, luz, agua, internet)
- $W_{com} = 0.3$ (Cercanía a escuelas, hospitales, supermercados del DENUE)
- $W_{riesg} = 0.3$ (Penalización por intersección con zonas inundables o de incendio)

El resultado final se reescalará a un rango de 0 a 100 y se asignará una paleta de color choropleth.

> **Nota (2026-07-18): la paleta cambió respecto a la especificación original.** Aquí se pedía una escala semafórica verde-amarillo-naranja-rojo. Se abandonó por dos razones. **(1) Colisión de significado:** las capas de riesgo ya usaban rojo para *peligro*, así que el mismo color decía "mala inversión", "poca cobertura de servicios" y "zona peligrosa" simultáneamente en el mismo mapa. **(2) Accesibilidad:** el par rojo-verde es el que peor funciona con deuteranopia (~8% de los hombres), y es justo el eje que esta capa necesita comunicar.
>
> La paleta vigente asigna una familia de color por significado — **rojo-ladrillo = peligro**, **ámbar-crema = valor (índice de inversión)**, **teal = cobertura de servicios** — con rampas **secuenciales** (oscuro→claro) en vez de divergentes, de modo que la luminosidad haga el trabajo y sigan leyéndose en escala de grises. Definidas en `index.html` (`ESCALONES_SERVICIOS`, `ESCALONES_INVERSION`, `COLORES_RIESGO`).
