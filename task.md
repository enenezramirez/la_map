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
- [x] Filtrar el mapa geoestadístico para obtener únicamente Saltillo, Ramos Arizpe y Arteaga. Implementado en `scripts/process_data.py` (`filtrar_marco_geoestadistico`). Por ahora solo Saltillo tiene datos (342 AGEBs); la config `MUNICIPIOS_AGEB` ya tiene entradas listas para Ramos Arizpe y Arteaga — solo falta agregar las rutas de sus carpetas de localidad cuando se descarguen. Salida intermedia en `raw_data/processed/ageb_filtrado.geojson` (EPSG:4326).
- [x] Procesar los datos de servicios del Censo e integrarlos por colonia/AGEB. Implementado en `scripts/process_data.py` (`cargar_censo_servicios`, `calcular_cobertura_servicios`, `integrar_censo_a_ageb`). Calcula % de electricidad, agua, drenaje e internet por AGEB (variables `VPH_C_ELEC`, `VPH_AGUADV`, `VPH_DRENAJ`, `VPH_INTER` sobre `TVIVHAB`) y un índice compuesto `SERVICIOS_INDEX` (promedio de los 4). Nota: el Censo agregado por AGEB no permite calcular "% viviendas con TODOS los servicios simultáneamente" (eso requeriría microdatos) — `SERVICIOS_INDEX` es la aproximación por promedio. 340/342 AGEBs de Saltillo con datos (2 sin match, probablemente no residenciales). Salida intermedia en `raw_data/processed/ageb_con_servicios.geojson`.
- [BLOQUEADO] Cruzar espacialmente los polígonos de colonias con las zonas de inundación del CENAPRED. Depende de la capa granular de inundación (ver Fase 1), aún no disponible. Se omite por ahora.
- [x] Exportar las capas resultantes a formato GeoJSON limpio en la carpeta `data/`. Implementado en `scripts/process_data.py` (`exportar_capa_servicios_basicos`): geometría simplificada (tolerancia 0.00005°) y solo columnas relevantes para el frontend. Resultado: `data/servicios_basicos.geojson`, 340 AGEBs, 477.8 KB (muy por debajo del límite de 5MB de `SPEC.md`), sin geometrías inválidas ni vacías. Falta aún la capa de inundación (bloqueada) y el Índice de Inversión (Fase 5).

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
