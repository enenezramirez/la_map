# GeoRiesgos Saltillo - Guía de Desarrollo para Claude Code

Este archivo proporciona contexto y comandos útiles para que tú (Claude) trabajes de forma eficiente en este proyecto.

## Estructura del Workspace
- `index.html` - Punto de entrada de la aplicación frontend (Leaflet.js).
- `styles.css` - Estilos de la aplicación (CSS Vanilla, enfoque moderno/oscuro).
- `data/` - Carpeta para archivos vectoriales y GeoJSON generados por Python.
- `scripts/` - Scripts de procesamiento de datos espaciales en Python (`GeoPandas`).
- `SPEC.md` - Especificación técnica y requerimientos del proyecto.
- `task.md` - Lista de tareas activas (actualízala conforme completes hitos).

## Comandos del Proyecto
- **Iniciar Servidor de Desarrollo:** `python -m http.server 8000` (Abre `http://localhost:8000` en tu navegador)
- **Ejecutar Procesamiento de Datos:** `python scripts/process_data.py`

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
