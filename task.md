# Lista de Tareas: GeoRiesgos Saltillo

Esta es la lista de tareas activas para el desarrollo del proyecto. Usa `[ ]` para tareas pendientes, `[/]` para tareas en progreso y `[x]` para completadas.

---

## Fase 1: Entorno de Desarrollo y Configuración Inicial
- [x] Configurar repositorio Git e inicializar commits (`git init`, `.gitignore`).
- [x] Crear el entorno virtual de Python (`venv`) e instalar dependencias (`pandas`, `geopandas`, `jupyter`, `shapely`, `pyproj`). Nota: se omitió `fiona` (sin wheel para Python 3.14 en Windows, requiere GDAL); GeoPandas 1.x usa `pyogrio` como motor de I/O por defecto, cubriendo la misma función.
- [/] Descargar los primeros conjuntos de datos brutos:
  - [/] Marco Geoestadístico de Coahuila (INEGI). Ya en `raw_data/marco_geoestadistico/saltillo_map_ageb/` — cubre únicamente municipio de Saltillo (localidad Saltillo ciudad con 342 AGEBs + 3 localidades rurales sin AGEB). Falta Ramos Arizpe y Arteaga.
  - [/] Censo de Población 2020 a nivel de AGEB/Manzana para Saltillo (INEGI). Descargado por el usuario, pendiente indicar la ruta local para integrarlo.
  - [BLOQUEADO] Capas de riesgos de inundación en Saltillo (CENAPRED). Solo se encontró el dataset "Indicadores Municipales de Peligro, Exposición y Vulnerabilidad" (`raw_data/cenapred_indicadores_municipales/`), que da un único valor agregado (`GP_INUNDAC = Alto`) para todo el municipio, sin granularidad por colonia/AGEB. Se retoma más adelante si aparece una fuente más detallada (Visor de Capas del Atlas Nacional o IMPLAN Saltillo).

## Fase 2: Procesamiento de Datos (Python & GeoPandas)
- [ ] Filtrar el mapa geoestadístico para obtener únicamente Saltillo, Ramos Arizpe y Arteaga.
- [ ] Procesar los datos de servicios del Censo e integrarlos por colonia/AGEB.
- [ ] Cruzar espacialmente los polígonos de colonias con las zonas de inundación del CENAPRED.
- [ ] Exportar las capas resultantes a formato GeoJSON limpio en la carpeta `data/`.

## Fase 3: Mapa Base Interactivo (Leaflet.js)
- [ ] Crear la estructura de la página en `index.html` importando Leaflet.js.
- [ ] Aplicar estilos premium en `styles.css` (tema oscuro, tipografía Inter, paneles flotantes glassmorphic).
- [ ] Programar en JavaScript la inicialización del mapa centrado en Saltillo y Ramos Arizpe.
- [ ] Implementar el control de capas base y el panel lateral interactivo.

## Fase 4: Integración de Capas en el Mapa
- [ ] Cargar los archivos GeoJSON locales usando Fetch API en JavaScript.
- [ ] Estilizar la capa de Servicios Básicos según el porcentaje de cobertura (de menor a mayor cobertura).
- [ ] Estilizar la capa de Riesgos Naturales (zonas rojas semitransparentes para inundación).
- [ ] Crear leyendas interactivas y tooltips informativos para el usuario al hacer clic en una zona.

## Fase 5: Algoritmo de Índice y Despliegue
- [ ] Programar la lógica del Scoring de inversión en Python y generar la capa consolidada.
- [ ] Agregar la capa del "Índice de Inversión" al mapa de Leaflet con una escala de color verde-rojo.
- [ ] Realizar pruebas locales finales levantando el servidor ligero de Python.
- [ ] Configurar GitHub Pages para desplegar el mapa en la web de manera gratuita.
