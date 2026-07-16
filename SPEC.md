# Especificación Técnica: GeoRiesgos Saltillo

Este documento sirve como la especificación del sistema (Single Source of Truth) para el desarrollo de la aplicación.

---

## 1. Requerimientos Funcionales

1. **Mapa Base Interactivo:**
   - Mapa centrado en la Zona Metropolitana de Saltillo (Saltillo, Ramos Arizpe y Arteaga, Coahuila).
   - Base de mapa estética en tonos oscuros o claros limpios (por ejemplo, CartoDB Positron o Stadia Maps).
2. **Visualización de Capas (Layers):**
   - **Capa 1: Riesgos de Inundación (CENAPRED):** Polígonos de zonas inundables coloreados semafóricamente (rojo/amarillo).
   - **Capa 2: Riesgo Forestal (CONABIO/CONAFOR):** Áreas con peligro de incendios, especialmente en las zonas boscosas de Arteaga.
   - **Capa 3: Cobertura de Servicios Básicos (INEGI Censo):** Porcentaje de viviendas con servicios completos (agua, luz, drenaje e internet) por sector.
   - **Capa 4: Riesgos Geológicos y Deslizamientos (CENAPRED - Evaluado):** Zonas propensas a deslaves en laderas (remoción de masa) y fallas geológicas locales identificadas.
3. **Índice de Inversión Inmobiliaria:**
   - Una capa combinada (Weighted Overlay) calculada en Python que sume los servicios básicos, penalice las zonas de riesgo (inundación, incendios y deslizamientos) y valore la cercanía a infraestructura.
4. **Panel de Control (UI/UX):**
   - Menú lateral responsivo con efecto glassmorphism.
   - Interruptores para capas e información emergente (tooltip/sidebar) al hacer clic en un sector.

### 1.1 Alcance Geográfico y Expansión Futura
* **Fase Inicial:** Saltillo, Ramos Arizpe y Arteaga (Zona Metropolitana de Saltillo).
* **Fase de Expansión:** Monterrey (Nuevo León), Torreón (Coahuila) y Monclova (Coahuila). La arquitectura debe ser modular para permitir añadir nuevas ciudades de forma sencilla reemplazando o sumando archivos GeoJSON independientes.

### 1.2 Legitimidad y Trazabilidad de los Datos
Dado que la precisión es crítica para la toma de decisiones inmobiliarias, la aplicación debe garantizar la procedencia de la información:
* **Metadatos Obligatorios:** Cada capa debe documentar estrictamente en su código/GeoJSON la **Fuente Oficial** y la **Fecha de Descarga/Actualización** (ej. *CENAPRED, corte a Diciembre 2025*).
* **UI Informativa:** Cuando el usuario haga clic en cualquier sector del mapa para ver los detalles, el panel de información debe mostrar visiblemente el origen y la fecha de corte de los datos de riesgo y servicios que está visualizando.

---

## 2. Arquitectura de Datos y Backend (Python)

El procesamiento de datos se ejecutará localmente y fuera de línea con Python.

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

El resultado final se reescalará a un rango de 0 a 100 y se asignará una paleta de color choropleth (verde, amarillo, naranja, rojo).
