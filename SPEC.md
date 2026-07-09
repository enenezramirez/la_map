# Especificación Técnica: GeoRiesgos Saltillo

Este documento sirve como la especificación del sistema (Single Source of Truth) para el desarrollo de la aplicación.

---

## 1. Requerimientos Funcionales

1. **Mapa Base Interactivo:**
   - Mapa centrado en Saltillo, Ramos Arizpe y Arteaga, Coahuila.
   - Base de mapa estética en tonos oscuros o claros limpios (por ejemplo, CartoDB Positron o Stadia Maps).
2. **Visualización de Capas (Layers):**
   - **Capa 1: Riesgos de Inundación (CENAPRED):** Polígonos de zonas inundables coloreados semafóricamente (rojo/amarillo).
   - **Capa 2: Riesgo Forestal (CONABIO):** Áreas boscosas de la periferia (como la Sierra de Arteaga) con vulnerabilidad a incendios.
   - **Capa 3: Cobertura de Servicios Básicos (INEGI Censo):** Colonias coloreadas por su porcentaje de viviendas con servicios completos (agua, luz, drenaje e internet).
3. **Índice de Inversión Inmobiliaria:**
   - Una capa calculada en Python que combine los servicios básicos, la cercanía a equipamiento urbano y penalice las áreas de alto riesgo natural.
   - Escala de color de verde (inversión recomendada) a rojo (riesgo o carencia de servicios).
4. **Panel de Control (UI/UX):**
   - Menú lateral o flotante responsivo con diseño moderno (efecto cristal/glassmorphism).
   - Interruptores (toggles) para activar/desactivar cada capa individualmente.
   - Leyendas claras que expliquen los colores de las capas.
   - Caja de información emergente (tooltip o sidebar) que muestre detalles específicos de la colonia o sector seleccionado al hacer clic.

---

## 2. Arquitectura de Datos y Backend (Python)

El procesamiento de datos se ejecutará localmente y fuera de línea con Python.

### Herramientas de Datos:
- `pandas` y `geopandas` para el manejo de dataframes espaciales.
- `shapely` para operaciones geométricas (ej. validar si una colonia intersecta una zona de inundación).
- `fiona` y `pyproj` para conversión de sistemas de coordenadas (EPSG:4326 a nivel global).

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
