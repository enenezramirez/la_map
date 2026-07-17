# GeoRiesgos Saltillo - Guía de Desarrollo para Claude Code

Este archivo proporciona contexto y comandos útiles para que la Inteligencia Artificial trabaje de forma eficiente en este proyecto.

## Resumen del Proyecto
GeoRiesgos Saltillo es una aplicación web interactiva (mapa) que cruza datos sociodemográficos y económicos para visualizar zonas de riesgo, vulnerabilidad y oportunidades de inversión en Saltillo, Coahuila.
- **Frontend:** HTML/JS Vanilla con Leaflet.js para el mapa y capas interactivas (estilo glassmorphism oscuro).
- **Backend/Datos:** Scripts en Python (`geopandas`, `pandas`) que procesan datos brutos del INEGI (Censo, cartografía vectorial de AGEB), DENUE e IMPLAN para generar archivos `.geojson` simplificados.

## Estructura del Workspace
- `index.html` - Punto de entrada de la aplicación frontend (Leaflet.js).
- `styles.css` - Estilos de la aplicación (CSS Vanilla, enfoque moderno/oscuro).
- `data/` - Carpeta para archivos vectoriales y GeoJSON generados por Python.
- `scripts/` - Scripts de procesamiento de datos espaciales en Python (`GeoPandas`).
- `SPEC.md` - Especificación técnica y requerimientos del proyecto.
- `task.md` - Lista de tareas activas (actualízala conforme completes hitos).
- `DATOS.md` - Bitácora de datos: procedencia de cada dataset (fuente oficial, fecha de corte y de descarga, licencia, uso y motivo de descarte). Requerida por `SPEC.md §1.2`; actualízala al agregar, cambiar o descartar cualquier fuente.

## Comandos del Proyecto
- **Iniciar Servidor de Desarrollo:** `python -m http.server 8000` (Abre `http://localhost:8000` en tu navegador)
- **Ejecutar Procesamiento de Datos:** `python scripts/process_data.py`. **Importante:** `geopandas` vive en el entorno virtual, no en el Python del sistema. En Windows usa el intérprete del `venv`: `venv\Scripts\python.exe scripts\process_data.py` (o activa el `venv` primero).

## Fuentes de Datos
> Procedencia completa y verificada de cada dataset en **`DATOS.md`**. Lo de abajo es solo el resumen.

- **INEGI:** *Información vectorial de localidades amanzanadas y números exteriores 2023* (polígonos AGEB y nombre de colonia), Censo de Población 2020 (servicios básicos) y DENUE 05_2026 (equipamiento urbano).
- **IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024** (fuente primaria de riesgo, SHP vectoriales): inundación pluvial urbana, deslizamientos traslacionales y riesgo químico-tecnológico (almacenamiento de sustancias peligrosas).
- **CONAGUA — ANRI** (respaldo): raster de severidad de inundación (Tr=100), conservado en `data/riesgo_inundacion.png` + `_meta.json`.
- **Capas generadas en `data/`:** `servicios_basicos.geojson`, `indice_inversion.geojson`, `riesgo_inundacion.geojson`, `riesgo_deslizamientos.geojson`, `riesgo_quimico.geojson`.

## Lineamientos de Codificación
1. **Frontend (HTML/JS):**
   - Usa JavaScript modular y limpio sin frameworks pesados (Vite/React no son necesarios por ahora).
   - Utiliza Leaflet.js para toda la lógica de mapas y capas.
   - Aplica estilos modernos con variables CSS (esquemas oscuros por defecto, transiciones suaves y estética de cristal/glassmorphism).
2. **Backend/Procesamiento (Python):**
   - Utiliza `pandas` and `geopandas` para manipular geometrías y atributos.
   - Todo el código debe estar debidamente documentado con docstrings e incluir Type Hints.
3. **Flujo de Trabajo:**
   - Lee el archivo `SPEC.md` antes de realizar cualquier cambio significativo.
   - Consulta `task.md`, trabaja en **una sola tarea** a la vez, y actualiza el archivo marcando la tarea como completada al finalizar.
