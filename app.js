// Initialize the map (the real center/zoom is set by fitBounds below)
const map = L.map('map', {
    zoomControl: false, // Hide the default buttons so we can position them ourselves
    // The risk layers are very dense multipolygons (dissolved from
    // ~12,700 polygons): rasterizing them on Canvas avoids SVG jank.
    preferCanvas: true
});

// Move the zoom control to the bottom-right so it doesn't clash with the menu
L.control.zoom({
    position: 'bottomright'
}).addTo(map);

// Initial framing: covers Saltillo, Ramos Arizpe and Arteaga
const REGION_BOUNDS = L.latLngBounds([
    [25.28, -101.08], // southwest (below Saltillo)
    [25.62, -100.80]  // northeast (above Ramos Arizpe / Arteaga)
]);
map.fitBounds(REGION_BOUNDS, { padding: [20, 20] });

// Add base layer - CartoDB Dark Matter (premium dark style)
const darkBaseLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// Alternative base layer - CartoDB Positron (premium light style, in case the user prefers light)
const lightBaseLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
});

// Base layer control (dark / light), bottom-left
const controlMapaBase = L.control.layers(
    { 'Oscuro': darkBaseLayer, 'Claro': lightBaseLayer },
    null,
    { position: 'bottomleft', collapsed: true }
).addTo(map);

// Leaflet builds this control as a bare <section>, which shows up in the
// landmark list as an unnamed region sitting inside the map, and names
// its toggle "Layers" in English on a page declared lang="es". Neither
// exists until the control is on the map, so it is patched here.
const contenedorMapaBase = controlMapaBase.getContainer();
contenedorMapaBase.querySelector('.leaflet-control-layers-list')
    .setAttribute('aria-label', 'Mapa base');
contenedorMapaBase.querySelector('.leaflet-control-layers-toggle')
    .setAttribute('title', 'Mapa base');

// Detail sidebar: open/close
const detailsSidebar = document.getElementById('details-sidebar');

// The card never leaves the DOM — it slides out and fades to
// `opacity: 0` — so hiding it from the eye does not hide it from the
// keyboard. Closed, it still held up to 16 focusable controls (the close
// button plus one per sector of the last colonia opened; ZONA CENTRO has
// 15), every one of them accepting focus with nothing on screen.
// `inert` is set with the class instead of after the slide-out, so
// keyboard reachability never depends on an animation finishing.
function abrirFicha() {
    detailsSidebar.classList.remove('sidebar-collapsed');
    detailsSidebar.inert = false;
}

function cerrarFicha() {
    // Read this before going inert, or the browser has already dropped
    // the focus we are trying to hand back.
    const teniaFoco = detailsSidebar.contains(document.activeElement);
    detailsSidebar.classList.add('sidebar-collapsed');
    detailsSidebar.inert = true;
    // Focus inside an inert subtree is dropped to <body>, which restarts
    // the tab sequence from the top of the page. Hand it to the map: it
    // is what the card was describing, and tabbing on from there reaches
    // the panel in its normal order.
    if (teniaFoco) document.getElementById('map').focus();
}

document.getElementById('close-sidebar').addEventListener('click', () => {
    cerrarFicha();
    // The outline marks whatever the card is describing, so closing the
    // card is what says "I am done with this zone". Leaving it behind
    // would mark a selection with nothing left to explain it.
    limpiarSeleccion();
});

// --- Shared choropleth and legend utilities (Phase 4/5) ---

// Escapes text before interpolating it into innerHTML templates.
// Today the GeoJSON files are generated locally by process_data.py from
// official SHP files (INEGI/IMPLAN) and served from the same origin, so
// there is no third-party input; this hardens the cards in case a layer
// ever comes from a remote URL or a user upload.
//
// **Contract: HTML text nodes and QUOTED attribute values only.** These
// five entities are enough for both, and that is every context this file
// uses it in. They are NOT enough for an unquoted attribute, a URL
// (`href`/`src`, where `javascript:` survives escaping) or a CSS context
// (`style="..."`, where `url(...)` does).
//
// This file no longer writes a style attribute anywhere — the legend
// swatches carry `data-swatch` and are colored through the CSSOM — but the
// CSS caveat still holds on the far side of that hop: whatever lands in
// data-swatch is assigned to `style.background`, so it must stay a
// hardcoded palette constant. esc() would not make a computed value safe
// there.
function esc(valor) {
    return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* Map color budget ("Traza" identity, 2026-07-18).
   Each family means ONE thing and only one:
     · brick-red    → DANGER   (risk layers)
     · amber-cream  → VALUE    (investment index)
     · teal         → COVERAGE (basic services)

   The three used to share the same green→red traffic-light ramp, so
   red meant "low coverage", "bad investment" and "dangerous zone" at
   the same time, on the same map. On top of that, the red-green pair
   is the one that works worst with deuteranopia (~8% of men): exactly
   the axis that matters most to read here.

   The ramps are SEQUENTIAL and all share the SAME direction as the
   risk layers: light = low, dark/intense = high. That gives the map a
   single reading rule. The indices used to run opposite to the risk
   layers (in the indices "high" was the lightest tone; in risk the
   darkest), and even with each legend beside it, the eye cannot hold
   two opposing rules on the same canvas: it confused people during
   presentations. Luminosity still does the work, so the ramps read in
   grayscale and for anyone who can't distinguish hues.

   The HIGH (dark) end uses deep but SATURATED tones, never close to the
   near-black background (#0b0c0e) —they are the same tones the identity
   had already chosen because they sit above the basemap—, so the top
   step is not lost; and the LOW end is now light, impossible to lose.
   Each AGEB also carries a faint border that outlines it even with a
   dark fill.

   Deliberate deviation from the original green-yellow-orange-red color
   spec; the reason is the unified color law explained above. */

// Ramps from low to high (light → dark): index 0 is the lowest value
// (light tone) and the last is the highest (dark tone), matching the
// risk layers. Services uses teal, Investment amber: they measure
// different things and can be on at the same time over the same AGEBs,
// so sharing a ramp made them indistinguishable.
const RAMPA_SERVICIOS = ['#7fd4c4', '#35a396', '#2a7d75', '#235a58', '#1d3a3c'];
const RAMPA_INVERSION = ['#f2d79c', '#d29b33', '#a87c27', '#7d5c22', '#4a3a24'];

// Cadastral value reuses the amber ramp on purpose. The color law is by
// MEANING, not by layer: amber-cream is the "value" family, and land value
// belongs to it as much as the investment index does. The legend already
// renders one block per active layer and warns when a ramp is shared, so
// the repetition is labelled rather than silent.
const RAMPA_CATASTRO = RAMPA_INVERSION;

// Breaks below read their colors from that ramp by index rather than
// repeating the hex codes, so the ramp really is the single source of truth
// it claims to be instead of a constant nobody references.

// Fixed pesos/m2 breaks, NOT quantiles. The other two layers use quantiles
// because their values are continuous and bunched; this one has just 14
// distinct values (one per terrain class), so quantiles would cut between
// identical figures and put the same class in two colors. Fixed breaks also
// keep the legend meaningful across editions: the tables are reissued yearly
// and the classes are reasonably stable, whereas a quantile cut would move
// under the reader's feet.
const ESCALONES_CATASTRO = [
    { hasta: 500, color: RAMPA_CATASTRO[0], etiqueta: 'Menos de $500' },
    { hasta: 800, color: RAMPA_CATASTRO[1], etiqueta: '$500 – $800' },
    { hasta: 1100, color: RAMPA_CATASTRO[2], etiqueta: '$800 – $1,100' },
    { hasta: 1500, color: RAMPA_CATASTRO[3], etiqueta: '$1,100 – $1,500' },
    { hasta: Infinity, color: RAMPA_CATASTRO[4], etiqueta: '$1,500 o más' }
];

// Neutral gray for "no data": neither good nor bad, and outside both
// ramps so it isn't confused with a low value.
const COLOR_SIN_DATO = '#3a3f47';

/* The breaks are computed by QUANTILES over the real data, not with
   fixed steps every 20 points. Reason: both indices are heavily skewed
   upward (the median for services is 91.7 and for investment 86.1), so
   with fixed breaks ~9 of every 10 AGEBs fell into the same class and
   the map was almost a single color: pretty and useless. By quantiles
   each class holds ~the same number of AGEBs and the real variation
   becomes visible.

   The price, worth keeping in mind when reading the map: the breaks
   depend on the data (they change if it changes), the labels end up on
   irregular numbers, and two nearly identical AGEBs can fall into
   different classes if the break passes right between them. In other
   words, the color shows RELATIVE POSITION within the city, not an
   absolute score. */
function escalonesPorCuantiles(valores, rampa, sufijo = '') {
    const datos = valores
        .filter(v => v !== null && v !== undefined && !Number.isNaN(v))
        .sort((a, b) => a - b);
    if (datos.length === 0) return [];

    const fmt = v => v.toFixed(1) + sufijo;
    const cuantil = p => datos[Math.min(datos.length - 1, Math.floor(p * datos.length))];

    const escalones = [];
    for (let i = rampa.length - 1; i >= 0; i--) {
        const minimo = i === 0 ? datos[0] : cuantil(i / rampa.length);
        const maximo = i === rampa.length - 1
            ? datos[datos.length - 1]
            : cuantil((i + 1) / rampa.length);
        // If two breaks coincide (many repeated values) the class
        // would be empty; skip it instead of showing a dead color
        // in the legend.
        if (escalones.length && minimo >= escalones[escalones.length - 1].minimo) continue;
        // How many sectors actually landed in the class, so the legend
        // help can state the real figure instead of promising an even
        // split that repeated values can break.
        const conteo = datos.filter(v => v >= minimo && v <= maximo).length;
        escalones.push({ minimo, color: rampa[i], conteo, etiqueta: `${fmt(minimo)} - ${fmt(maximo)}` });
    }
    return escalones;
}

// Filled when each GeoJSON loads (they depend on the data).
let ESCALONES_SERVICIOS = [];
let ESCALONES_INVERSION = [];

// --- IMPLAN risk layers (CARTO SALTILLO, 2024 Risk Atlas) ---
// Single-hue ramp (brick) by intensity level (INTENSIDAD field): the
// higher the intensity, the darker and more saturated. Used for flood,
// landslide and chemical-technological risk.
const COLORES_RIESGO = {
    'Muy alto': '#8c2b18',
    'Alto': '#b8452a',
    'Medio': '#d9743f',
    'Bajo': '#e8a86f',
    'Muy bajo': '#f0cfa8'
};
const ORDEN_RIESGO = ['Muy alto', 'Alto', 'Medio', 'Bajo', 'Muy bajo'];

function crearEstiloRiesgo() {
    return feature => ({
        fillColor: COLORES_RIESGO[feature.properties.INTENSIDAD] || '#9ca3af',
        weight: 1,
        color: 'rgba(255, 255, 255, 0.25)',
        fillOpacity: 0.6
    });
}

// Short layer name for the help disclosure. Several legends can be on
// screen at once, so "what do these levels mean?" repeated three times
// named nothing: it read as one help for the whole map. Naming the layer
// in the summary is also what a screen reader announces when tabbing
// between the disclosures, where the surrounding legend title is not
// part of the accessible name.
const NOMBRE_CORTO_CAPA = {
    servicios: 'Servicios',
    inversion: 'Inversión',
    inundacion: 'Inundación',
    deslizamientos: 'Deslizamientos',
    quimico: 'Riesgo Químico'
};

// What each risk layer measures and which levels it leaves out. Only
// the part that cannot be read off the data lives here; the levels and
// their counts are computed from the GeoJSON at load.
const AYUDA_RIESGO = {
    inundacion: {
        mide: 'Acumulación de agua de lluvia en zona urbana.',
        omite: 'Se omite el nivel «Muy bajo», que es el fondo del modelo y cubre casi toda la mancha urbana.',
        indice: 'Es la única capa de riesgo que penaliza el Índice de Inversión.'
    },
    deslizamientos: {
        mide: 'Movimiento de material ladera abajo sobre una superficie de falla (traslacional).',
        omite: 'Se omite el nivel «Muy bajo», que es el fondo del modelo.',
        indice: 'Capa informativa: no modifica ningún índice.'
    },
    quimico: {
        mide: 'Exposición al almacenamiento de sustancias químicas peligrosas.',
        omite: 'Se omiten «Muy bajo» y también «Bajo»: este último cubre el 93% de la malla del modelo, así que no distingue unas zonas de otras.',
        indice: 'Capa informativa: no modifica ningún índice.'
    }
};

// Help sits at the end of every legend, always in the same place, so it
// can be found the same way for any layer.
function htmlAyudaRiesgo(clave, conteos) {
    const a = AYUDA_RIESGO[clave];
    if (!a) return '';
    const presentes = ORDEN_RIESGO.filter(n => conteos.has(n));
    const listaNiveles = presentes.map(n =>
        `<li><strong>${esc(n)}</strong> — ${conteos.get(n).toLocaleString('es-MX')} zonas</li>`).join('');
    // The scales are not comparable between layers, and saying so is the
    // whole point: "Medio" is the worst level mapped for landslides but
    // the mildest one shown for chemical risk.
    const peor = presentes[0];
    return `
        <details class="legend-help">
            <summary>¿Qué significan los niveles de ${esc(NOMBRE_CORTO_CAPA[clave] || '')}?</summary>
            <div class="legend-help-body">
                <p><strong>Qué mide:</strong> ${esc(a.mide)}</p>
                <p><strong>Niveles en esta capa:</strong></p>
                <ul class="help-levels">${listaNiveles}</ul>
                <p>En esta capa el nivel más severo que aparece es <strong>${esc(peor)}</strong>.
                   Los niveles son la clasificación del propio IMPLAN; este proyecto no la recalcula,
                   y los umbrales que separan un nivel del siguiente no vienen en los archivos publicados.
                   <strong>No son comparables entre capas:</strong> un «Medio» de una capa no equivale
                   al «Medio» de otra.</p>
                <p>${esc(a.omite)}</p>
                <p>${esc(a.indice)}</p>
                <p>Es un modelo a escala urbana para comparar zonas, <strong>no un estudio de sitio</strong>:
                   no sustituye un dictamen para un predio concreto. Cubre solo el municipio de Saltillo.</p>
            </div>
        </details>
    `;
}

// Legend for a risk layer: only the levels present + the source/cutoff
// date (for data traceability), taken from the loaded GeoJSON.
function htmlLeyendaRiesgo(titulo, clave, conteos, fuente, fecha) {
    const filas = ORDEN_RIESGO.filter(n => conteos.has(n)).map(n => `
        <div class="legend-row">
            <span class="legend-swatch" data-swatch="${COLORES_RIESGO[n]}"></span>
            <span>${esc(n)}</span>
        </div>
    `).join('');
    const src = fuente
        ? `<p class="legend-source">Fuente: ${esc(fuente)}${fecha ? ' · ' + esc(fecha) : ''}.</p>`
        : '';
    return `<p class="legend-title">${esc(titulo)}</p>${filas}${src}${htmlAyudaRiesgo(clave, conteos)}`;
}

// Pre-built legend HTML per risk layer (filled on load).
const leyendasRiesgo = { inundacion: null, deslizamientos: null, quimico: null };

// --- Locate the colonia of a point (point-in-polygon) ----------------
// The IMPLAN risk layers carry no zone name: they are an intensity
// model and, on top of that, are dissolved by level, so a single shape
// covers half the city. To answer "which colonia is this?" on click, we
// locate the point inside the AGEBs (which do have COLONIA) with our own
// ray-casting: ~340 polygons and an isolated click, so it isn't worth
// adding a dependency like Turf.js.

// AGEB index for lookups, with a precomputed bounding box to quickly
// discard most of them without walking their vertices.
let agebsParaConsulta = null;

function calcularBbox(geometria) {
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    const poligonos = geometria.type === 'MultiPolygon'
        ? geometria.coordinates
        : [geometria.coordinates];
    for (const poligono of poligonos) {
        for (const [lng, lat] of poligono[0]) {
            if (lng < minLng) minLng = lng;
            if (lng > maxLng) maxLng = lng;
            if (lat < minLat) minLat = lat;
            if (lat > maxLat) maxLat = lat;
        }
    }
    return [minLng, minLat, maxLng, maxLat];
}

function indexarAgebs(geojson) {
    agebsParaConsulta = geojson.features
        .filter(f => f.geometry && f.properties.COLONIA)
        .map(f => ({
            colonia: f.properties.COLONIA,
            municipio: f.properties.NOM_MUN,
            geometria: f.geometry,
            bbox: calcularBbox(f.geometry)
        }));
}

// Ray casting over a ring: counts crossings of a horizontal ray toward
// the east; odd = inside. GeoJSON coordinates [lng, lat].
function puntoEnAnillo([x, y], anillo) {
    let dentro = false;
    for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
        const [xi, yi] = anillo[i];
        const [xj, yj] = anillo[j];
        const cruzaLatitud = (yi > y) !== (yj > y);
        if (cruzaLatitud && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
            dentro = !dentro;
        }
    }
    return dentro;
}

// A GeoJSON polygon is [outer ring, ...holes]: the point counts if it
// falls inside the outer ring and outside every hole.
function puntoEnPoligono(punto, anillos) {
    if (!puntoEnAnillo(punto, anillos[0])) return false;
    return !anillos.slice(1).some(hueco => puntoEnAnillo(punto, hueco));
}

function puntoEnGeometria(punto, geometria) {
    if (geometria.type === 'Polygon') {
        return puntoEnPoligono(punto, geometria.coordinates);
    }
    if (geometria.type === 'MultiPolygon') {
        return geometria.coordinates.some(p => puntoEnPoligono(punto, p));
    }
    return false;
}

// Returns the AGEB that contains the point, or null if it falls outside
// all of them (risk zones extend beyond the urban footprint covered by
// AGEBs, so this is expected, not an error).
function buscarAgebEnPunto(latlng) {
    if (!agebsParaConsulta) return null;
    const punto = [latlng.lng, latlng.lat];
    for (const ageb of agebsParaConsulta) {
        const [minLng, minLat, maxLng, maxLat] = ageb.bbox;
        if (punto[0] < minLng || punto[0] > maxLng || punto[1] < minLat || punto[1] > maxLat) {
            continue;
        }
        if (puntoEnGeometria(punto, ageb.geometria)) return ageb;
    }
    return null;
}

// Detail card when clicking a risk zone: colonia (if the point falls
// in an AGEB), intensity + source and cutoff date (for traceability).
function mostrarDetalleRiesgo(props, latlng) {
    const ageb = buscarAgebEnPunto(latlng);
    document.getElementById('sector-title').textContent = ageb ? ageb.colonia : props.TITULO;

    // With no AGEB there are two distinct causes that must not be
    // confused: the AGEBs haven't loaded yet (the click arrived first)
    // or the point truly falls outside the urban footprint.
    let filaUbicacion;
    if (ageb) {
        filaUbicacion = `<p class="detail-row"><span>Municipio</span><strong>${esc(ageb.municipio)}</strong></p>`;
    } else if (!agebsParaConsulta) {
        filaUbicacion = '<p class="detail-row"><span>Colonia</span><strong>Cargando…</strong></p>';
    } else {
        filaUbicacion = '<p class="detail-row"><span>Ubicación</span><strong>Fuera de zona urbana</strong></p>';
    }
    document.getElementById('sector-info').innerHTML = `
        ${filaUbicacion}
        <p class="detail-row"><span>Fenómeno</span><strong>${esc(props.FENOMENO)}</strong></p>
        <p class="detail-row detail-index"><span>Nivel de riesgo</span><strong>${esc(props.INTENSIDAD)}</strong></p>
        <p class="detail-source">Fuente: ${esc(props.FUENTE)}. Corte: ${esc(props.FECHA)}.</p>
    `;
    abrirFicha();
}

function sinDato(valor) {
    return valor === null || valor === undefined || Number.isNaN(valor);
}

// `obtenerEscalones` is a getter, not an array: the breaks are computed
// when the GeoJSON loads and the style is evaluated later, feature by feature.
function crearFuncionColor(obtenerEscalones) {
    return valor => {
        if (sinDato(valor)) return COLOR_SIN_DATO;
        const escalones = obtenerEscalones();
        // With no breaks there is no scale to apply (would happen if a
        // whole layer arrived without data). This used to blow up with a
        // TypeError reading .color of undefined and crashed the render.
        if (escalones.length === 0) return COLOR_SIN_DATO;
        const escalon = escalones.find(e => valor >= e.minimo);
        return escalon ? escalon.color : escalones[escalones.length - 1].color;
    };
}

function crearEstiloCapa(campoValor, funcionColor) {
    return feature => {
        const valor = feature.properties[campoValor];
        return {
            fillColor: funcionColor(valor),
            weight: 1,
            color: 'rgba(255, 255, 255, 0.25)',
            // AGEBs with no data are drawn fainter: present and
            // clickable (the card explains why there's no data), but
            // without visually competing with those that do measure something.
            fillOpacity: sinDato(valor) ? 0.35 : 0.65
        };
    };
}

// The synthetic indices are the opposite case to the risk layers: the
// number is absolute, the colour is relative. Saying which is which is
// the point of this help, because the two are read off the same map.
const AYUDA_INDICE = {
    servicios: {
        mide: 'Promedio de cuatro coberturas del Censo 2020 en cada sector: electricidad, agua entubada, drenaje e internet.',
        unidad: 'El número es un porcentaje: 90 significa 90% de cobertura promedio, y eso no cambia nunca.'
    },
    inversion: {
        mide: 'Combina el Índice de Servicios (peso 0.4) con la cercanía a escuelas, salud y supermercados (peso 0.3), y le resta una penalización por exposición a inundación (hasta 30 puntos).',
        unidad: 'El número va de 0 a 100 y es absoluto: no depende de cómo estén los demás sectores.'
    }
};

function htmlAyudaIndice(clave, escalones, nSinDato) {
    const a = AYUDA_INDICE[clave];
    if (!a) return '';
    const porClase = escalones.length ? Math.round(
        escalones.reduce((n, e) => n + (e.conteo || 0), 0) / escalones.length) : 0;
    const reparto = porClase
        ? `Cada clase agrupa aproximadamente el mismo número de sectores (~${porClase}).`
        : 'Cada clase agrupa aproximadamente el mismo número de sectores.';
    return `
        <details class="legend-help">
            <summary>¿Qué significa el color de ${esc(NOMBRE_CORTO_CAPA[clave] || '')}?</summary>
            <div class="legend-help-body">
                <p><strong>Qué mide:</strong> ${esc(a.mide)}</p>
                <p><strong>El número:</strong> ${esc(a.unidad)}</p>
                <p><strong>El color, en cambio, es relativo.</strong> Los cortes se calculan por
                   cuantiles sobre los sectores de la ciudad, así que el color dice
                   <em>en qué lugar queda este sector frente a los demás</em>, no si está bien o mal
                   en términos absolutos. ${esc(reparto)}</p>
                <p>Dos consecuencias que conviene tener presentes: los cortes cambian si cambian los
                   datos, y dos sectores con valores casi idénticos pueden caer en clases distintas
                   si el corte pasa justo entre ellos.</p>
                ${nSinDato > 0 ? `<p><strong>Gris:</strong> ${nSinDato} ${nSinDato === 1 ? 'sector' : 'sectores'} sin dato publicado.
                   No es un cero: al hacer clic, la ficha dice el motivo.</p>` : ''}
            </div>
        </details>
    `;
}

function htmlLeyenda(titulo, escalones, nSinDato = 0, clave = null) {
    if (escalones.length === 0) return `<p class="empty-legend">Cargando…</p>`;
    const filas = escalones.map(e => `
        <div class="legend-row">
            <span class="legend-swatch" data-swatch="${e.color}"></span>
            <span>${esc(e.etiqueta)}</span>
        </div>
    `).join('');
    const filaSinDato = nSinDato > 0 ? `
        <div class="legend-row">
            <span class="legend-swatch" data-swatch="${COLOR_SIN_DATO}"></span>
            <span>Sin datos (${nSinDato})</span>
        </div>
    ` : '';
    const nota = '<p class="legend-source">Cortes por cuantiles: el color indica posición relativa dentro de la ciudad, no una calificación absoluta.</p>';
    return `<p class="legend-title">${esc(titulo)}</p>${filas}${filaSinDato}${nota}${htmlAyudaIndice(clave, escalones, nSinDato)}`;
}

// Legend registry per layer. EVERY active layer gets its own block:
// showing only the most recently activated one meant the reader had
// several layers painted on the map and a legend describing just one of
// them, with no sign of which — and the help below it reported counts
// and levels belonging to that one layer only.
const SIN_DATO_CONTEO = { servicios: 0, inversion: 0 };

const LEYENDAS = {
    servicios: () => htmlLeyenda('Índice de Servicios Básicos', ESCALONES_SERVICIOS, SIN_DATO_CONTEO.servicios, 'servicios'),
    inversion: () => htmlLeyenda('Índice de Inversión Inmobiliaria', ESCALONES_INVERSION, SIN_DATO_CONTEO.inversion, 'inversion'),
    inundacion: () => leyendasRiesgo.inundacion || '<p class="empty-legend">Cargando…</p>',
    deslizamientos: () => leyendasRiesgo.deslizamientos || '<p class="empty-legend">Cargando…</p>',
    quimico: () => leyendasRiesgo.quimico || '<p class="empty-legend">Cargando…</p>',
    // Replaced by cargarCapaCatastro once the lookup arrives, since its class
    // counts are only known then.
    catastro: () => '<p class="empty-legend">Cargando…</p>'
};

// Which risk layers share the single-hue brick ramp: their swatches are
// colored by LEVEL, not by layer, so two risk legends on screen show the
// same color meaning two different things.
const CLAVES_RIESGO = new Set(['inundacion', 'deslizamientos', 'quimico']);

const capasActivas = new Set();

// Panel order, read off the DOM, is the legend order. Activation order
// would reshuffle the blocks on every toggle, moving the help away from
// where it was found last time (WCAG 2.2 SC 3.2.6 Consistent Help), and
// reading the legend against the switches above would mean hunting. The
// sequence is derived rather than hardcoded so it still holds if the
// panel is regrouped into sections.
const checkboxPorClave = new Map();

function registrarClaveDeCapa(clave, checkbox) {
    checkboxPorClave.set(clave, checkbox);
}

function ordenDePanel(claves) {
    const enPanel = Array.from(document.querySelectorAll('.layer-control input[type="checkbox"]'));
    return claves.slice().sort((a, b) =>
        enPanel.indexOf(checkboxPorClave.get(a)) - enPanel.indexOf(checkboxPorClave.get(b)));
}

// The help panes are re-rendered along with the legend, so an open one
// would snap shut just because another layer was toggled — irrelevant
// when a single legend existed, annoying now that reading one layer's
// help while turning another on is the normal case. The state is read
// back off the DOM, which needs no bookkeeping of its own.
function ayudasAbiertas() {
    return new Set(Array.from(document.querySelectorAll('#legend-container .legend-block'))
        .filter(bloque => {
            const ayuda = bloque.querySelector('details');
            return ayuda && ayuda.open;
        })
        .map(bloque => bloque.dataset.capa));
}

function actualizarLeyenda() {
    const contenedor = document.getElementById('legend-container');
    if (capasActivas.size === 0) {
        contenedor.innerHTML = '<p class="empty-legend">Activa o haz clic en una zona para ver los detalles.</p>';
        return;
    }
    const abiertas = ayudasAbiertas();
    const claves = ordenDePanel(Array.from(capasActivas));

    // Named up front, because labelling each block is not enough here:
    // the brick ramp is shared, so "Medio" is literally the same swatch
    // in two legends while meaning a different thing in each.
    const nRiesgo = claves.filter(k => CLAVES_RIESGO.has(k)).length;
    const aviso = nRiesgo > 1
        ? `<p class="legend-note">${nRiesgo} capas de riesgo activas. Cada bloque explica la suya:
           los colores se repiten entre capas, y un «Medio» de una no equivale al «Medio» de otra.</p>`
        : '';

    contenedor.innerHTML = aviso + claves.map(clave =>
        `<div class="legend-block" data-capa="${esc(clave)}">${LEYENDAS[clave]()}</div>`).join('');

    // Each swatch carries its color in data-swatch and gets it applied here,
    // rather than arriving as a `style="background:…"` attribute. A style
    // attribute in markup is governed by the CSP (style-src-attr), so keeping
    // one would have forced 'unsafe-inline' into style-src for three spans;
    // assigning through the CSSOM is not subject to the policy at all.
    // The color still comes from the JS palette, which is the point: the map
    // polygons read the same constants, and a second copy in the stylesheet
    // would be a second source of truth for the color law, free to drift.
    // The hex test is the invariant stated mechanically instead of trusted to a
    // comment: only a palette-shaped literal is ever assigned, so this fails
    // closed (an uncolored swatch) if a computed value ever reaches data-swatch.
    for (const muestra of contenedor.querySelectorAll('.legend-swatch[data-swatch]')) {
        const color = muestra.dataset.swatch;
        if (/^#[0-9a-f]{3,8}$/i.test(color)) muestra.style.background = color;
    }

    for (const bloque of contenedor.querySelectorAll('.legend-block')) {
        const ayuda = bloque.querySelector('details');
        if (ayuda && abiertas.has(bloque.dataset.capa)) ayuda.open = true;
    }
}

function marcarCapaActiva(clave) {
    capasActivas.add(clave);
    actualizarLeyenda();
}

function marcarCapaInactiva(clave) {
    capasActivas.delete(clave);
    // With nothing left on the map the outline marks nothing: no
    // choropleth, no risk zones, just basemap. While ANY layer is still
    // on it keeps doing its job — it says where the zone the card
    // describes was, which is half the reason to turn a noisy layer off
    // in the first place — so this only fires on the empty map.
    if (capasActivas.size === 0) limpiarSeleccion();
    actualizarLeyenda();
}

// --- Layer availability by visible area ------------------------------
// When navigating outside a layer's coverage (e.g. to Arteaga, where
// there are no AGEBs yet), its toggle is disabled and explained instead
// of leaving the map empty for no reason. Coverage is derived from the
// real bbox of the already-loaded GeoJSON (capa.getBounds()), never from
// a zoom or a hardcoded rectangle, so the state keeps working on its own
// when data from new municipalities is added.
const capasEnVista = [];

function registrarCapaEnVista(checkbox, capa) {
    const control = checkbox.closest('.layer-control');
    const statusEl = document.createElement('p');
    statusEl.className = 'layer-status';
    statusEl.id = `layer-status-${checkbox.id}`;
    statusEl.textContent = 'Sin datos en la zona visible del mapa.';
    control.appendChild(statusEl);
    // The native disabled attribute would take the switch out of the tab
    // order entirely, which contradicts the rule this feature was built
    // on — disable and explain, never hide. aria-disabled keeps it
    // reachable and announced; this guard is what actually stops the
    // toggle, for pointer and for the space bar alike.
    checkbox.closest('.switch-container').addEventListener('click', e => {
        if (checkbox.getAttribute('aria-disabled') === 'true') e.preventDefault();
    });
    capasEnVista.push({ checkbox, control, capa, statusEl });
    actualizarDisponibilidadCapas();
}

function actualizarDisponibilidadCapas() {
    const vista = map.getBounds();
    for (const { checkbox, control, capa, statusEl } of capasEnVista) {
        const bounds = capa.getBounds();
        const hayDatos = bounds.isValid() && vista.intersects(bounds);
        checkbox.setAttribute('aria-disabled', hayDatos ? 'false' : 'true');
        // Only point at the note while it is actually shown: a hidden
        // description is still read by most screen readers, and it would
        // claim "no data here" over the whole city.
        if (hayDatos) checkbox.removeAttribute('aria-describedby');
        else checkbox.setAttribute('aria-describedby', statusEl.id);
        control.classList.toggle('sin-datos-vista', !hayDatos);
    }
}

map.on('moveend', actualizarDisponibilidadCapas);

// A missing value is shown as a dash, not as 0: "I don't know" and "it
// is zero" are different statements and the map must not confuse them.
const SIN_VALOR = '—';
const formatoEntero = valor => sinDato(valor) ? SIN_VALOR : Number(valor).toLocaleString('es-MX');
const formatoPct = valor => sinDato(valor) ? SIN_VALOR : `${Number(valor).toFixed(1)}%`;
const formatoIndice = valor => sinDato(valor) ? SIN_VALOR : Number(valor).toFixed(1);

// Note explaining why an AGEB has no index (no dwellings, figures
// masked for confidentiality, or absent from the Census).
function htmlMotivoSinDato(props) {
    return props.MOTIVO_SIN_DATO
        ? `<p class="detail-source">Sin dato de servicios: ${esc(props.MOTIVO_SIN_DATO)}.</p>`
        : '';
}

// When the card is opened from a street search, the searched street is
// stated on it, and so is a mismatch between the settlement INEGI
// records for that block front and the colonia the map assigns to the
// sector. They disagree for 42.1% of street fronts, because an AGEB
// routinely spans several settlements and the map keeps the dominant
// one. Saying it is better than a card that silently contradicts the
// result the user just clicked.
function htmlContextoCalle(contexto, colonia) {
    if (!contexto) return '';
    const asentamientos = contexto.asentamientos || [];
    const otros = asentamientos.filter(a => a !== colonia);
    let nota = '';
    if (otros.length === asentamientos.length && otros.length) {
        // None of the recorded settlements is the one the sector is
        // published under.
        nota = `<p class="detail-note">Ese tramo está en ${asentamientos.length === 1 ? 'el asentamiento' : 'los asentamientos'} <strong>${esc(listaEsp(asentamientos))}</strong>. El sector se publica bajo <strong>${esc(colonia)}</strong>, el asentamiento predominante del AGEB.</p>`;
    } else if (otros.length) {
        // The card's own title is one of them; the rest still deserve
        // saying, or the merged zone would hide names it really carries.
        nota = `<p class="detail-note">Esta vialidad también se registra en <strong>${esc(listaEsp(otros))}</strong>, dentro del mismo sector.</p>`;
    }
    const cps = contexto.cps || [];
    return `
        <p class="detail-row"><span>Vialidad</span><strong>${esc(contexto.tipoVia)} ${esc(contexto.calle)}</strong></p>
        ${cps.length ? `<p class="detail-row"><span>Código postal</span><strong>${esc(cps.join(' · '))}</strong></p>` : ''}
        ${nota}
    `;
}

function mostrarDetalleSector(props, contextoCalle) {
    document.getElementById('sector-title').textContent = props.COLONIA;
    document.getElementById('sector-info').innerHTML = `
        ${htmlContextoCalle(contextoCalle, props.COLONIA)}
        <p class="detail-row"><span>Municipio</span><strong>${esc(props.NOM_MUN)}</strong></p>
        <p class="detail-row"><span>Población total</span><strong>${formatoEntero(props.POBTOT)}</strong></p>
        <p class="detail-row"><span>Viviendas habitadas</span><strong>${formatoEntero(props.TVIVHAB)}</strong></p>
        <h3>Cobertura de Servicios Básicos</h3>
        <p class="detail-row"><span>Electricidad</span><strong>${formatoPct(props.PCT_ELECTRICIDAD)}</strong></p>
        <p class="detail-row"><span>Agua entubada</span><strong>${formatoPct(props.PCT_AGUA)}</strong></p>
        <p class="detail-row"><span>Drenaje</span><strong>${formatoPct(props.PCT_DRENAJE)}</strong></p>
        <p class="detail-row"><span>Internet</span><strong>${formatoPct(props.PCT_INTERNET)}</strong></p>
        <p class="detail-row detail-index"><span>Índice de Servicios</span><strong>${formatoIndice(props.SERVICIOS_INDEX)}</strong></p>
        ${htmlMotivoSinDato(props)}
    `;
    abrirFicha();
}

function mostrarDetalleInversion(props) {
    document.getElementById('sector-title').textContent = props.COLONIA;
    document.getElementById('sector-info').innerHTML = `
        <p class="detail-row"><span>Municipio</span><strong>${esc(props.NOM_MUN)}</strong></p>
        <p class="detail-row"><span>Índice de Servicios</span><strong>${formatoIndice(props.SERVICIOS_INDEX)}</strong></p>
        <h3>Cercanía a Equipamiento Urbano</h3>
        <p class="detail-row"><span>Escuelas</span><strong>${formatoIndice(props.SCORE_ESCUELA)}</strong></p>
        <p class="detail-row"><span>Salud</span><strong>${formatoIndice(props.SCORE_SALUD)}</strong></p>
        <p class="detail-row"><span>Supermercados</span><strong>${formatoIndice(props.SCORE_SUPERMERCADO)}</strong></p>
        <p class="detail-row"><span>Índice de Comercios</span><strong>${formatoIndice(props.COMERCIOS_INDEX)}</strong></p>
        <p class="detail-row"><span>Riesgo de inundación (−)</span><strong>${formatoIndice(props.RIESGO_INDEX)}</strong></p>
        <p class="detail-row detail-index"><span>Índice de Inversión</span><strong>${formatoIndice(props.INVERSION_INDEX)}</strong></p>
        ${htmlMotivoSinDato(props)}
    `;
    abrirFicha();
}

function cargarCapaChoropleth({ archivo, checkbox, clave, campoValor, configEscala, funcionEstilo, funcionDetalle, alCargarGeojson }) {
    let capa = null;
    // Registered before the fetch, so the legend order is settled from
    // the start and does not depend on which GeoJSON arrives first.
    registrarClaveDeCapa(clave, checkbox);

    // `no-cache` revalidates the GeoJSON with the server (avoids serving
    // a stale version after regenerating the data with process_data.py).
    fetch(archivo, { cache: 'no-cache' })
        .then(respuesta => respuesta.json())
        .then(geojson => {
            if (alCargarGeojson) alCargarGeojson(geojson);

            // The breaks come from the data that just arrived, so they
            // are computed here, before styling anything.
            if (configEscala) {
                const valores = geojson.features.map(f => f.properties[campoValor]);
                configEscala.asignar(
                    escalonesPorCuantiles(valores, configEscala.rampa, configEscala.sufijo)
                );
                SIN_DATO_CONTEO[clave] = valores.filter(sinDato).length;
            }

            capa = L.geoJSON(geojson, {
                style: funcionEstilo,
                onEachFeature: (feature, layer) => {
                    layer.on({
                        mouseover: e => e.target.setStyle({ weight: 2, color: '#ffffff', fillOpacity: 0.8 }),
                        mouseout: e => capa.resetStyle(e.target),
                        click: e => {
                            resaltarGeometrias([e.target.feature.geometry]);
                            funcionDetalle(e.target.feature.properties);
                        }
                    });
                }
            });

            if (checkbox.checked) {
                capa.addTo(map);
                marcarCapaActiva(clave);
            }

            registrarCapaEnVista(checkbox, capa);
        })
        .catch(error => console.error(`Error loading layer "${archivo}":`, error));

    checkbox.addEventListener('change', () => {
        if (!capa) return;
        if (checkbox.checked) {
            capa.addTo(map);
            capa.bringToFront();
            marcarCapaActiva(clave);
        } else {
            map.removeLayer(capa);
            marcarCapaInactiva(clave);
        }
    });
}

// Loader for IMPLAN risk layers (categorical choropleth by INTENSIDAD).
// Builds its legend from the levels present and the source/date of the
// GeoJSON itself.
function cargarCapaRiesgo({ archivo, checkbox, clave, titulo }) {
    let capa = null;
    registrarClaveDeCapa(clave, checkbox);

    fetch(archivo, { cache: 'no-cache' })
        .then(respuesta => respuesta.json())
        .then(geojson => {
            // Counted, not just listed: how many zones each level covers
            // is what tells the reader whether a level is the exception
            // or the rule in this layer.
            const conteos = new Map();
            for (const f of geojson.features) {
                const n = f.properties.INTENSIDAD;
                conteos.set(n, (conteos.get(n) || 0) + 1);
            }
            const props0 = geojson.features.length ? geojson.features[0].properties : {};
            leyendasRiesgo[clave] = htmlLeyendaRiesgo(titulo, clave, conteos, props0.FUENTE, props0.FECHA);

            capa = L.geoJSON(geojson, {
                style: crearEstiloRiesgo(),
                onEachFeature: (feature, layer) => {
                    layer.on({
                        mouseover: e => e.target.setStyle({ weight: 2, color: '#ffffff', fillOpacity: 0.75 }),
                        mouseout: e => capa.resetStyle(e.target),
                        click: e => {
                            resaltarGeometrias([e.target.feature.geometry]);
                            mostrarDetalleRiesgo(e.target.feature.properties, e.latlng);
                        }
                    });
                }
            });

            if (checkbox.checked) {
                capa.addTo(map);
                capa.bringToFront();
                marcarCapaActiva(clave);
            }

            registrarCapaEnVista(checkbox, capa);
        })
        .catch(error => console.error(`Error loading layer "${archivo}":`, error));

    checkbox.addEventListener('change', () => {
        if (!capa) return;
        if (checkbox.checked) {
            capa.addTo(map);
            capa.bringToFront();
            marcarCapaActiva(clave);
        } else {
            map.removeLayer(capa);
            marcarCapaInactiva(clave);
        }
    });
}

// --- Cadastral land value (Tesorería Municipal) ---------------------
// Informational layer: it does NOT feed the Investment Index. A low land
// value is genuinely ambiguous for a buyer — cheap entry or weak area — so
// giving it a sign in the score would bake in an undeclared thesis.
//
// It is the only layer with no geometry file of its own. The figures are
// published per colonia, so data/valor_catastral.json is a lookup keyed by
// AGEB and the polygons come from the ones the services layer already
// fetched. A third copy of the AGEB geometry would have cost ~640 KB against
// the 5 MB budget of SPEC §2, which data/ is already close to.
let catastroMeta = null;

function colorCatastro(valor) {
    if (valor === null || valor === undefined) return COLOR_SIN_DATO;
    return (ESCALONES_CATASTRO.find(e => valor < e.hasta) || ESCALONES_CATASTRO.at(-1)).color;
}

function htmlAyudaCatastro(conteos, sinDato) {
    const presentes = Object.entries(conteos).sort((a, b) => b[1] - a[1]);
    const lista = presentes.map(([clase, n]) => `${esc(clase)} (${n})`).join(', ');
    return `
        <details class="legend-help">
            <summary>¿Qué significa este valor?</summary>
            <div class="legend-help-body">
                <p><strong>Es un valor catastral, no un precio de mercado.</strong> Es la base
                   que el municipio usa para cobrar el impuesto predial, y en México se fija
                   deliberadamente <em>por debajo</em> de lo que cuesta el suelo en realidad.
                   No sirve para estimar en cuánto se vende un terreno.</p>
                <p><strong>Es una clase de toda la colonia, no un avalúo del predio.</strong>
                   El municipio asigna a cada colonia un <em>tipo de terreno</em> y a cada tipo
                   un precio por m². Dos predios muy distintos de la misma colonia reciben la
                   misma cifra.</p>
                <p><strong>Clases presentes:</strong> ${lista}.</p>
                <p><strong>Gris:</strong> ${sinDato} ${sinDato === 1 ? 'sector' : 'sectores'} sin
                   valor publicado. No es un cero: al hacer clic, la ficha dice el motivo. Las
                   tablas cubren <strong>solo el municipio de Saltillo</strong>.</p>
            </div>
        </details>
    `;
}

function htmlLeyendaCatastro(conteos, sinDato) {
    const filas = ESCALONES_CATASTRO.map(e => `
        <div class="legend-row">
            <span class="legend-swatch" data-swatch="${e.color}"></span>
            <span>${esc(e.etiqueta)}</span>
        </div>
    `).join('');
    const gris = sinDato > 0 ? `
        <div class="legend-row">
            <span class="legend-swatch" data-swatch="${COLOR_SIN_DATO}"></span>
            <span>Sin valor publicado (${sinDato})</span>
        </div>
    ` : '';
    const fuente = catastroMeta
        ? `<p class="legend-source">Fuente: ${esc(catastroMeta.fuente)} · ${esc(catastroMeta.edicion)}. Pesos por m².</p>`
        : '';
    return `<p class="legend-title">Valor Catastral del Suelo</p>${filas}${gris}${fuente}`
        + htmlAyudaCatastro(conteos, sinDato);
}

function mostrarDetalleCatastro(props) {
    const dato = props.CATASTRO;
    document.getElementById('sector-title').textContent = props.COLONIA || 'Sector sin colonia';

    let cuerpo;
    if (!dato) {
        // Why there is no figure matters: "no row in the tables" and "this
        // municipality is not covered" are different facts, and neither is a
        // zero. Same principle as MOTIVO_SIN_DATO in the services card.
        const motivo = String(props.NOM_MUN || '').toUpperCase() === 'SALTILLO'
            ? `La colonia <strong>${esc(props.COLONIA || 'de este sector')}</strong> no aparece
               en las tablas de valores del municipio. Puede ser un desarrollo posterior a la
               edición vigente, un nombre registrado de otra forma, o suelo no residencial.`
            : `Las tablas de valores son del <strong>municipio de Saltillo</strong>, y este
               sector está en <strong>${esc(props.NOM_MUN || 'otro municipio')}</strong>.`;
        cuerpo = `<p class="detail-note">Sin valor catastral publicado. ${motivo}</p>`;
    } else {
        // Say WHY the two names differ rather than lumping both cases into one
        // phrase: "same words, different order" is simply false of a spacing
        // difference, and the note exists to stop the card from quietly
        // contradicting the name on the map.
        const motivoAlias = dato.via === 'espacios'
            ? 'escrito junto o separado distinto'
            : 'mismas palabras, otro orden';
        const alias = dato.nombre_catastro
            ? `<p class="detail-note">El catastro registra esta colonia como
               <strong>${esc(dato.nombre_catastro)}</strong> (${motivoAlias}).</p>`
            : '';
        // `if (!dato)` above says nothing about `dato.valor`, and null is a
        // state the pipeline can reach: a class present in the colonia table
        // but missing from the value table exports as null. That happened
        // during this layer's own development. Unguarded it is worse than a
        // blank: the map still paints (grey), the legend still counts the
        // sector under its class, and only the click throws — from inside a
        // Leaflet handler, after the title was already replaced, leaving the
        // new colonia's name sitting above the previous colonia's figures.
        // Checking the type also keeps this the one interpolation that does
        // not reach innerHTML through esc(): toLocaleString on a non-number
        // is Object.prototype's, which returns the string unchanged.
        const cifra = Number.isFinite(dato.valor)
            ? `$${dato.valor.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
            : 'Sin cifra publicada';
        cuerpo = `
            <div class="detail-row"><span>Tipo de terreno</span><strong>${esc(dato.clase)}</strong></div>
            <div class="detail-row"><span>Valor por m²</span><strong>${esc(cifra)}</strong></div>
            ${alias}
            <p class="detail-note"><strong>Valor catastral (base fiscal), no precio de mercado.</strong>
               Es una clase asignada a toda la colonia, no un avalúo de este predio.</p>
        `;
    }

    document.getElementById('sector-info').innerHTML = `
        ${cuerpo}
        <p class="detail-source">Fuente: ${esc(catastroMeta ? catastroMeta.fuente : 'Tesorería Municipal de Saltillo')}
           · Edición ${esc(catastroMeta ? catastroMeta.edicion : '2026')}.</p>
    `;
    abrirFicha();
}

function cargarCapaCatastro(checkbox) {
    let capa = null;
    registrarClaveDeCapa('catastro', checkbox);

    // Needs both the lookup and the AGEB polygons, which arrive from a
    // different request; whichever lands second starts the work.
    Promise.all([
        fetch('data/valor_catastral.json', { cache: 'no-cache' }).then(r => r.json()),
        agebsListos
    ]).then(([catastro, geojson]) => {
        catastroMeta = { fuente: catastro.fuente, edicion: catastro.edicion };

        const conteos = {};
        let sinDato = 0;
        const features = geojson.features.map(f => {
            // hasOwn, not a truthiness check: `sectores` comes from JSON.parse
            // and carries Object.prototype, so a key like "constructor" would
            // hand back an inherited function — truthy, and it would sail past
            // the `if (!dato)` guard in the card.
            const dato = Object.hasOwn(catastro.sectores, f.properties.CVEGEO)
                ? catastro.sectores[f.properties.CVEGEO] : null;
            if (dato) conteos[dato.clase] = (conteos[dato.clase] || 0) + 1;
            else sinDato++;
            return { ...f, properties: { ...f.properties, CATASTRO: dato } };
        });

        LEYENDAS.catastro = () => htmlLeyendaCatastro(conteos, sinDato);

        capa = L.geoJSON({ type: 'FeatureCollection', features }, {
            style: f => ({
                fillColor: colorCatastro(f.properties.CATASTRO && f.properties.CATASTRO.valor),
                weight: 1, opacity: 1, color: 'rgba(255,255,255,0.25)', fillOpacity: 0.65
            }),
            onEachFeature: (feature, layer) => {
                layer.on({
                    mouseover: e => e.target.setStyle({ weight: 2, color: '#ffffff', fillOpacity: 0.8 }),
                    mouseout: e => capa.resetStyle(e.target),
                    click: e => {
                        resaltarGeometrias([e.target.feature.geometry]);
                        mostrarDetalleCatastro(e.target.feature.properties);
                    }
                });
            }
        });

        if (checkbox.checked) {
            capa.addTo(map);
            marcarCapaActiva('catastro');
        }
        registrarCapaEnVista(checkbox, capa);
    }).catch(error => console.error('Error loading cadastral values:', error));

    checkbox.addEventListener('change', () => {
        if (!capa) return;
        if (checkbox.checked) {
            capa.addTo(map);
            capa.bringToFront();
            marcarCapaActiva('catastro');
        } else {
            map.removeLayer(capa);
            marcarCapaInactiva('catastro');
        }
    });
}

// --- Colonia search ------------------------------------------------
// Jump to a colonia by name. The colonia names and geometries already
// live in the services GeoJSON (indexed as AGEBs on load), so the search
// index is built from that same data with no extra request.
const buscadorInput = document.getElementById('colonia-search');
const buscadorSugerencias = document.getElementById('colonia-suggestions');
const buscadorLimpiar = document.getElementById('colonia-search-clear');

// One entry per real colonia: its combined bbox (a colonia spans several
// AGEBs) and the AGEB geometries used to draw the selection highlight.
let indiceColonias = [];
// Mixed: colonia and street results share one list and one keyboard path.
let resultadosFiltrados = [];
let sugerenciaActiva = -1;
// One selection at a time, whether it came from the search or from a
// click on the map.
let capaSeleccion = null;

// Placeholder labels are not real places; keep them out of the search.
const COLONIAS_NO_BUSCABLES = new Set(['SIN NOMBRE REGISTRADO', 'Sin nombre de colonia']);

// "A", "A y B", "A, B y C" — a merged zone can carry up to 7 settlement
// names, and a bare join reads as a list of separate places.
function listaEsp(valores) {
    if (valores.length <= 1) return valores[0] || '';
    return valores.slice(0, -1).join(', ') + ' y ' + valores[valores.length - 1];
}

// Fold accents and case so "peñas" matches "penas" and "Centro" "centro",
// and fold punctuation to a single space, because nobody types the
// period in "FRANCISCO I. MADERO" or "ALFREDO V. BONFIL" — 76 street
// names carry one, and a plain substring match made every one of them
// unreachable unless the punctuation was typed exactly.
const normalizarTexto = t => t
    .normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').trim();

function construirIndiceColonias(geojson) {
    const grupos = new Map();
    for (const f of geojson.features) {
        const colonia = f.properties.COLONIA;
        if (!colonia || COLONIAS_NO_BUSCABLES.has(colonia) || !f.geometry) continue;
        const municipio = f.properties.NOM_MUN || '';
        const clave = `${colonia}|${municipio}`;
        let g = grupos.get(clave);
        if (!g) {
            g = { colonia, municipio, sectores: [], bbox: [Infinity, Infinity, -Infinity, -Infinity] };
            grupos.set(clave, g);
        }
        // Keep each AGEB's own geometry and properties: a colonia can
        // span several of them (27% do, up to 15 in ZONA CENTRO), and
        // the detail card reports one AGEB, never a fabricated average.
        g.sectores.push({ geometria: f.geometry, props: f.properties });
        const [minLng, minLat, maxLng, maxLat] = calcularBbox(f.geometry);
        if (minLng < g.bbox[0]) g.bbox[0] = minLng;
        if (minLat < g.bbox[1]) g.bbox[1] = minLat;
        if (maxLng > g.bbox[2]) g.bbox[2] = maxLng;
        if (maxLat > g.bbox[3]) g.bbox[3] = maxLat;
    }
    indiceColonias = Array.from(grupos.values());
    indiceColonias.sort((a, b) => a.colonia.localeCompare(b.colonia, 'es'));
    for (const g of indiceColonias) g.normalizado = normalizarTexto(g.colonia);
}

// AGEB by CVEGEO. The street index stores only these keys, never
// geometry, and resolves position through the polygons already loaded.
const agebsPorClave = new Map();

// The services layer is the source of colonia names; when it loads we
// both index the AGEBs (for risk-click lookups) and build the search.
// The cadastral layer has no geometry of its own and borrows these polygons,
// so it waits on this instead of re-fetching them.
let anunciarAgebs;
const agebsListos = new Promise(resolver => { anunciarAgebs = resolver; });

function alCargarAgebs(geojson) {
    indexarAgebs(geojson);
    construirIndiceColonias(geojson);
    agebsPorClave.clear();
    for (const f of geojson.features) {
        if (f.geometry) agebsPorClave.set(f.properties.CVEGEO, { geometria: f.geometry, props: f.properties });
    }
    buscadorInput.disabled = false;
    anunciarAgebs(geojson);
}

// --- Street index (INEGI Frente de manzana) -------------------------
// INEGI already pairs street and settlement in the same record, so the
// index needs no geometry: each zone lists the AGEBs it touches and the
// browser resolves position from the polygons it already has.
//
// It is fetched lazily, on the first search, for two reasons: it is
// useless until someone types, and keeping it off the initial load means
// it never competes with the layer budget SPEC §2 sets for the map.
let indiceCalles = null;
let cargaCalles = null;

// Shape of the zone tuples this parser understands. Must match
// FORMATO_INDICE_CALLES in scripts/process_data.py.
//
// It exists because the failure it prevents was observed for real: the
// index is fetched with `no-cache`, so a regenerated file reaches the
// page immediately — including a page that is itself a cached older
// version. An older parser reading a newer shape did not throw, it
// resolved lookups to `undefined` and printed "undefined · SALTILLO"
// into the suggestion list. Refusing an unknown version turns that into
// an honest, visible failure: the street search goes unavailable and
// says why, and the colonia search carries on.
const FORMATO_INDICE_CALLES = 2;

function cargarIndiceCalles() {
    if (cargaCalles) return cargaCalles;
    // `cache: 'no-cache'` for the same reason as the map layers: it
    // revalidates with the server instead of trusting a stale copy.
    // It matters more here — this file's SHAPE changes between
    // versions, so a returning visitor holding an old copy would not
    // just see old streets, the parser would throw on it and the whole
    // street search would go quiet. (Observed exactly that in testing.)
    cargaCalles = fetch('data/calles.json', { cache: 'no-cache' })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(json => {
            if (json.formato !== FORMATO_INDICE_CALLES) {
                throw new Error(
                    `formato ${json.formato} no reconocido (esta página entiende ` +
                    `${FORMATO_INDICE_CALLES}); recarga forzada para actualizarla`);
            }
            indiceCalles = {
                meta: { fuente: json.fuente, fecha: json.fecha_corte },
                calles: json.calles.map(([nombre, zonas]) => ({
                    nombre,
                    normalizado: normalizarTexto(nombre),
                    // A zone is one road type over one set of sectors.
                    // Settlements and postal codes are lists because the
                    // pipeline merges the zones that open the same
                    // sectors: several names, one place.
                    zonas: zonas.map(([t, asen, m, cps, agebs]) => ({
                        tipoVia: json.tipos[t],
                        asentamientos: asen.map(i => json.asentamientos[i]),
                        municipio: json.municipios[m],
                        cps: cps.map(i => json.cps[i]),
                        claves: agebs.map(i => json.agebs[i])
                    }))
                }))
            };
            return indiceCalles;
        })
        .catch(err => {
            // A failed street index must not take the colonia search
            // down with it: null means "streets unavailable", and the
            // next keystroke retries.
            console.error('No se pudo cargar el índice de calles:', err);
            cargaCalles = null;
            return null;
        });
    return cargaCalles;
}

function filtrarColonias(q) {
    const encontrados = [];
    for (const g of indiceColonias) {
        const pos = g.normalizado.indexOf(q);
        if (pos !== -1) {
            encontrados.push({
                pos, clase: 'colonia', orden: 0,
                titulo: g.colonia, subtitulo: g.municipio, etiqueta: 'COLONIA',
                datos: g
            });
        }
    }
    return encontrados;
}

function filtrarCalles(q) {
    if (!indiceCalles) return [];
    const encontrados = [];
    for (const calle of indiceCalles.calles) {
        const pos = calle.normalizado.indexOf(q);
        if (pos === -1) continue;
        // One row per street, never per zone: "LUIS ECHEVERRÍA" runs
        // through 64 settlements, and 64 rows would bury everything
        // else. Where it goes is what the card answers.
        const tipos = new Set(calle.zonas.map(z => z.tipoVia));
        const unica = calle.zonas.length === 1 ? calle.zonas[0] : null;
        encontrados.push({
            pos, clase: 'calle', orden: 1,
            titulo: calle.nombre,
            // "Tramos", not "asentamientos": after the merge a zone can
            // carry several settlement names, so counting zones is not
            // counting names. And a merged zone with many names is
            // counted rather than listed — spelling out seven of them
            // produces a truncated blob that labels nothing, which is
            // the very problem this row is meant to solve.
            subtitulo: !unica
                ? `${calle.zonas.length} tramos`
                : unica.asentamientos.length <= 2
                    ? `${listaEsp(unica.asentamientos)} · ${unica.municipio}`
                    : `${unica.asentamientos.length} asentamientos · ${unica.municipio}`,
            // A street name can carry more than one road type across the
            // city (778 do), and then no single one is true.
            etiqueta: tipos.size === 1 ? [...tipos][0] : 'VIALIDAD',
            datos: calle
        });
    }
    return encontrados;
}

function filtrarTodo(consulta) {
    const q = normalizarTexto(consulta.trim());
    if (!q) return [];
    const encontrados = filtrarColonias(q).concat(filtrarCalles(q));
    // Prefix matches first, then colonias before streets at equal
    // footing, then alphabetical; cap the list so it stays scannable.
    encontrados.sort((a, b) =>
        (a.pos - b.pos) || (a.orden - b.orden) || a.titulo.localeCompare(b.titulo, 'es'));
    return encontrados.slice(0, 8);
}

// Opening and closing the list is a state of the combobox, not just a
// visual effect, so it is announced through aria-expanded.
function cerrarSugerencias() {
    buscadorSugerencias.hidden = true;
    buscadorInput.setAttribute('aria-expanded', 'false');
    buscadorInput.removeAttribute('aria-activedescendant');
    sugerenciaActiva = -1;
}

function renderSugerencias(lista) {
    resultadosFiltrados = lista;
    sugerenciaActiva = -1;
    buscadorInput.removeAttribute('aria-activedescendant');
    if (lista.length === 0) {
        buscadorSugerencias.innerHTML = '';
        cerrarSugerencias();
        return;
    }
    // Each option needs an id so aria-activedescendant can point at it:
    // that is what tells a screen reader which suggestion the arrow keys
    // landed on, since focus itself never leaves the input.
    //
    // The kind tag is inside the option, so it is part of the name a
    // screen reader announces: with colonias and streets in one list,
    // the name alone would not say which is which.
    // Two lines, and the name gets the first one to itself. On one line
    // the settlement label — up to 439px for "ZONA DE AMORTIGUAMIENTO DE
    // LA SIERRA DE ZAPALINAMÉ III · Saltillo" — took all the room and
    // left the street name 0px in 4 of 8 rows, so "COLA DE PESCADO"
    // rendered as nothing and three different streets all read "NI…".
    // The name is what was searched for; the settlement is context.
    buscadorSugerencias.innerHTML = lista.map((r, i) => `
        <li class="search-suggestion" role="option" id="colonia-opcion-${i}"
            aria-selected="false" data-i="${i}">
            <span class="suggestion-name">${esc(r.titulo)}</span>
            <span class="suggestion-meta">
                <span class="suggestion-kind">${esc(r.etiqueta)}</span>
                <span class="suggestion-mun">${esc(r.subtitulo)}</span>
            </span>
        </li>
    `).join('');
    buscadorSugerencias.hidden = false;
    buscadorInput.setAttribute('aria-expanded', 'true');
}

// The selection is drawn as a SEPARATE overlay rather than by restyling
// the clicked feature. That is what makes it work on the risk layers,
// which render to a canvas and reset their style on mouseout, and it
// keeps one selection alive across layer toggles: nothing here depends
// on the feature's own style surviving.
//
// A cased line — dark casing under an amber core — because a single
// color cannot stay visible over this map. Amber alone vanishes against
// the SECOND CLASS OF EVERY RAMP (investment #d29b33 at 1.12:1, services
// #35a396 at 1.10:1, risk #d9743f at 1.16:1) and white alone vanishes
// against the light ones (1.22-1.51:1). Casing puts the contrast inside
// the line: core against casing is 7.16:1 whatever it is drawn over, and
// no fill can hide both at once since the two are 7.16:1 apart.
function resaltarGeometrias(geometrias) {
    limpiarSeleccion();
    const coleccion = {
        type: 'FeatureCollection',
        features: geometrias.map(geom => ({ type: 'Feature', geometry: geom, properties: {} }))
    };
    // No fill, so the choropleth underneath stays readable, and
    // non-interactive so it never intercepts a click meant for a layer.
    const contorno = (color, weight) => L.geoJSON(coleccion, {
        interactive: false,
        style: { color, weight, fill: false }
    });
    capaSeleccion = L.layerGroup([
        contorno('#0b0c0e', 6),   // casing (identity background)
        contorno('#c8912f', 2.5)  // core: the identity's selection amber
    ]).addTo(map);
    // In insertion order, so the core ends up above its own casing.
    capaSeleccion.eachLayer(capa => capa.bringToFront());
}

function limpiarSeleccion() {
    if (capaSeleccion) {
        map.removeLayer(capaSeleccion);
        capaSeleccion = null;
    }
}

// A colonia can cover several AGEBs, and an AGEB is the unit every
// figure in this app is measured on. Rather than average them into a
// number no source backs, the card lists the sectors and lets one be
// chosen. 212 of the 290 searchable colonias are a single AGEB, so most
// searches go straight to the data.
function mostrarSectoresDeColonia(g, contextoCalle) {
    const sectores = g.sectores.slice()
        .sort((a, b) => String(a.props.CVEGEO).localeCompare(String(b.props.CVEGEO)));
    document.getElementById('sector-title').textContent = g.colonia;
    document.getElementById('sector-info').innerHTML = `
        ${htmlContextoCalle(contextoCalle, g.colonia)}
        <p class="detail-row"><span>Municipio</span><strong>${esc(g.municipio)}</strong></p>
        <p class="detail-row"><span>Sectores (AGEB)</span><strong>${sectores.length}</strong></p>
        <h3>Elige un sector</h3>
        <p class="sector-hint">Los datos del Censo se publican por sector, no por colonia.</p>
        <ul class="sector-list">
            ${sectores.map((s, i) => `
                <li>
                    <button type="button" class="sector-btn">
                        <span class="sector-btn-name">Sector ${i + 1}</span>
                        <span class="sector-btn-meta">${formatoEntero(s.props.POBTOT)} hab · servicios ${formatoIndice(s.props.SERVICIOS_INDEX)}</span>
                    </button>
                </li>
            `).join('')}
        </ul>
    `;
    // Paired by position, not by a key round-tripped through the DOM:
    // a lookup that misses would quietly show another sector's figures,
    // and a plausible wrong number is the worst failure this app has.
    document.getElementById('sector-info').querySelectorAll('.sector-btn').forEach((btn, i) => {
        btn.addEventListener('click', () => {
            resaltarGeometrias([sectores[i].geometria]);
            // Carry the street context down: narrowing to one sector
            // must not drop which street brought the user here.
            mostrarDetalleSector(sectores[i].props, contextoCalle);
        });
    });
    abrirFicha();
}

function seleccionarColonia(g) {
    if (!g) return;
    const bounds = L.latLngBounds([[g.bbox[1], g.bbox[0]], [g.bbox[3], g.bbox[2]]]);
    // maxZoom keeps a tiny colonia from snapping to street level.
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    resaltarGeometrias(g.sectores.map(s => s.geometria));
    buscadorInput.value = g.colonia;
    cerrarSugerencias();
    buscadorLimpiar.hidden = false;
    // Opening the card is what gives a keyboard user a route to the
    // data at all: the layers are drawn on a canvas, so the polygons
    // have no DOM node to focus and the map's figures were reachable
    // by mouse only.
    if (g.sectores.length === 1) mostrarDetalleSector(g.sectores[0].props);
    else mostrarSectoresDeColonia(g);
}

// --- Selecting a street ---------------------------------------------
// A zone is one (street, settlement) pair. Its AGEBs are looked up in
// the layer already loaded; any key with no polygon is dropped rather
// than drawn as an empty selection.
function sectoresDeZona(zona) {
    return zona.claves
        .map(clave => agebsPorClave.get(clave))
        .filter(Boolean);
}

function encuadrarYResaltar(sectores) {
    if (!sectores.length) return;
    const caja = [Infinity, Infinity, -Infinity, -Infinity];
    for (const s of sectores) {
        const [minLng, minLat, maxLng, maxLat] = calcularBbox(s.geometria);
        if (minLng < caja[0]) caja[0] = minLng;
        if (minLat < caja[1]) caja[1] = minLat;
        if (maxLng > caja[2]) caja[2] = maxLng;
        if (maxLat > caja[3]) caja[3] = maxLat;
    }
    map.fitBounds(L.latLngBounds([[caja[1], caja[0]], [caja[3], caja[2]]]),
                  { padding: [40, 40], maxZoom: 16 });
    resaltarGeometrias(sectores.map(s => s.geometria));
}

// Opening a zone reuses the colonia machinery: one AGEB goes straight to
// its figures, several show the sector chooser, because every number in
// this app is published per AGEB and averaging them would invent data.
function abrirZonaDeCalle(calle, zona) {
    const sectores = sectoresDeZona(zona);
    encuadrarYResaltar(sectores);
    const contexto = { calle: calle.nombre, tipoVia: zona.tipoVia,
                       asentamientos: zona.asentamientos, cps: zona.cps };
    if (sectores.length === 1) mostrarDetalleSector(sectores[0].props, contexto);
    else if (sectores.length > 1) {
        mostrarSectoresDeColonia({
            colonia: listaEsp(zona.asentamientos), municipio: zona.municipio, sectores
        }, contexto);
    }
}

function mostrarTramosDeCalle(calle) {
    const zonas = calle.zonas.slice().sort((a, b) =>
        a.asentamientos[0].localeCompare(b.asentamientos[0], 'es'));
    const municipios = [...new Set(zonas.map(z => z.municipio))];
    document.getElementById('sector-title').textContent = calle.nombre;
    document.getElementById('sector-info').innerHTML = `
        <p class="detail-row"><span>Municipio</span><strong>${esc(municipios.join(', '))}</strong></p>
        <p class="detail-row"><span>Tramos</span><strong>${zonas.length}</strong></p>
        <h3>Elige un tramo</h3>
        <p class="sector-hint">Una vialidad puede cruzar varios asentamientos; los datos del Censo se publican por sector. Los tramos que caen en el mismo sector aparecen juntos.</p>
        <ul class="sector-list">
            ${zonas.map(z => `
                <li>
                    <button type="button" class="sector-btn">
                        <span class="sector-btn-name">${esc(z.tipoVia)} · ${esc(listaEsp(z.asentamientos))}</span>
                        <span class="sector-btn-meta">${esc(z.municipio)} · CP ${esc(z.cps.join(' · '))} · ${z.claves.length} sector${z.claves.length === 1 ? '' : 'es'}</span>
                    </button>
                </li>
            `).join('')}
        </ul>
        <p class="detail-source">Fuente: ${esc(indiceCalles.meta.fuente)}. Corte: ${esc(indiceCalles.meta.fecha)}.</p>
    `;
    // Paired by position, like the sector list: a key round-tripped
    // through the DOM could miss and quietly open another zone.
    document.getElementById('sector-info').querySelectorAll('.sector-btn').forEach((btn, i) => {
        btn.addEventListener('click', () => abrirZonaDeCalle(calle, zonas[i]));
    });
    abrirFicha();
}

function seleccionarCalle(calle) {
    buscadorInput.value = calle.nombre;
    cerrarSugerencias();
    buscadorLimpiar.hidden = false;
    if (calle.zonas.length === 1) {
        abrirZonaDeCalle(calle, calle.zonas[0]);
        return;
    }
    // Frame the whole street first, so the card's list of settlements
    // is read against the extent it actually covers.
    const todos = calle.zonas.flatMap(sectoresDeZona);
    encuadrarYResaltar(todos);
    mostrarTramosDeCalle(calle);
}

function seleccionarResultado(r) {
    if (!r) return;
    if (r.clase === 'calle') seleccionarCalle(r.datos);
    else seleccionarColonia(r.datos);
}

function limpiarBusqueda() {
    buscadorInput.value = '';
    buscadorLimpiar.hidden = true;
    resultadosFiltrados = [];
    cerrarSugerencias();
    limpiarSeleccion();
}

function moverSugerencia(delta) {
    const items = buscadorSugerencias.querySelectorAll('.search-suggestion');
    if (!items.length) return;
    sugerenciaActiva = (sugerenciaActiva + delta + items.length) % items.length;
    items.forEach((el, i) => {
        const activo = i === sugerenciaActiva;
        el.classList.toggle('active', activo);
        // The class is only paint; aria-selected and the pointer below
        // are what a screen reader actually reads.
        el.setAttribute('aria-selected', activo ? 'true' : 'false');
    });
    buscadorInput.setAttribute('aria-activedescendant', items[sugerenciaActiva].id);
    items[sugerenciaActiva].scrollIntoView({ block: 'nearest' });
}

buscadorInput.addEventListener('input', () => {
    const consulta = buscadorInput.value;
    renderSugerencias(filtrarTodo(consulta));
    buscadorLimpiar.hidden = consulta.length === 0;
    // Colonias answer from memory; streets need the lazy index. Re-run
    // the query when it lands, but only if the box still holds the same
    // text — otherwise a slow response would overwrite what the user
    // has typed since.
    if (!indiceCalles && consulta.trim()) {
        cargarIndiceCalles().then(indice => {
            if (indice && buscadorInput.value === consulta) {
                renderSugerencias(filtrarTodo(consulta));
            }
        });
    }
});

buscadorInput.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moverSugerencia(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moverSugerencia(-1); }
    else if (e.key === 'Enter') {
        // Only commits while the list is open. Enter used to fall back
        // to the first suggestion even after Escape had dismissed it,
        // so a keyboard user's cancel was not honoured.
        if (buscadorSugerencias.hidden) return;
        e.preventDefault();
        const idx = sugerenciaActiva >= 0 ? sugerenciaActiva : 0;
        seleccionarResultado(resultadosFiltrados[idx]);
    } else if (e.key === 'Escape') {
        cerrarSugerencias();
    }
});

// WCAG 2.2 SC 2.4.11 (Focus Not Obscured): the list only closed on an
// outside click, so tabbing out of the search left it open on top of
// the layer switches — the next control received focus completely
// hidden behind it. Closing on focus-out fixes it at the source.
document.getElementById('search-section').addEventListener('focusout', e => {
    if (!e.relatedTarget || !e.relatedTarget.closest('#search-section')) cerrarSugerencias();
});

buscadorSugerencias.addEventListener('click', e => {
    const li = e.target.closest('.search-suggestion');
    if (li) seleccionarResultado(resultadosFiltrados[Number(li.dataset.i)]);
});

buscadorLimpiar.addEventListener('click', limpiarBusqueda);

// Close the dropdown when clicking anywhere outside the search box.
document.addEventListener('click', e => {
    if (!e.target.closest('#search-section')) cerrarSugerencias();
});

cargarCapaChoropleth({
    archivo: 'data/servicios_basicos.geojson',
    checkbox: document.getElementById('layer-services'),
    clave: 'servicios',
    campoValor: 'SERVICIOS_INDEX',
    configEscala: {
        rampa: RAMPA_SERVICIOS,
        sufijo: '%',
        asignar: escalones => { ESCALONES_SERVICIOS = escalones; }
    },
    funcionEstilo: crearEstiloCapa('SERVICIOS_INDEX', crearFuncionColor(() => ESCALONES_SERVICIOS)),
    funcionDetalle: mostrarDetalleSector,
    // This layer's AGEBs are also the reference for locating the colonia
    // of a click on the risk layers, and the source of the colonia
    // search index. Both are built on load (alCargarAgebs), regardless
    // of whether the layer is visible.
    alCargarGeojson: alCargarAgebs
});

cargarCapaChoropleth({
    archivo: 'data/indice_inversion.geojson',
    checkbox: document.getElementById('layer-investment'),
    clave: 'inversion',
    campoValor: 'INVERSION_INDEX',
    configEscala: {
        rampa: RAMPA_INVERSION,
        asignar: escalones => { ESCALONES_INVERSION = escalones; }
    },
    funcionEstilo: crearEstiloCapa('INVERSION_INDEX', crearFuncionColor(() => ESCALONES_INVERSION)),
    funcionDetalle: mostrarDetalleInversion
});

// Layer 1 — Flood Risk (IMPLAN CARTO, 2024 Atlas): vector.
cargarCapaRiesgo({
    archivo: 'data/riesgo_inundacion.geojson',
    checkbox: document.getElementById('layer-floods'),
    clave: 'inundacion',
    titulo: 'Riesgo de Inundación Pluvial'
});

// Layer 4 — Landslide Risk (IMPLAN CARTO, 2024 Atlas): vector.
cargarCapaRiesgo({
    archivo: 'data/riesgo_deslizamientos.geojson',
    checkbox: document.getElementById('layer-landslides'),
    clave: 'deslizamientos',
    titulo: 'Riesgo de Deslizamientos'
});

// Layer 5 — Chemical-Technological Risk (IMPLAN CARTO, 2024 Atlas): vector.
// Only Medio+Alto (see NIVELES_ELEVADOS_QUIMICO in process_data.py).
cargarCapaRiesgo({
    archivo: 'data/riesgo_quimico.geojson',
    checkbox: document.getElementById('layer-chemical'),
    clave: 'quimico',
    titulo: 'Riesgo Químico-Tecnológico'
});

// Cadastral land value (Tesorería Municipal, 2026). Informational only:
// it does not enter the Investment Index. Borrows the AGEB polygons from the
// services layer, so it declares no file of its own.
cargarCapaCatastro(document.getElementById('layer-cadastral'));

// Backup (ANRI - CONAGUA): the flood layer by Tr=100 severity is kept
// as a raster in data/riesgo_inundacion.png (+_meta.json). To reactivate
// it as an imageOverlay, load meta.bounds and use L.imageOverlay(...).
// IMPLAN is the primary source (local, vector).

console.log("Leaflet initialized successfully.");
