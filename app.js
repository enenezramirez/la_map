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

// --- The visitor's own CARTO key (optional) -------------------------------
// CARTO watermarks its basemaps unless a key travels as ?key=. No key ships
// with this public repository: a visitor can paste their own, which stays in
// their browser (localStorage) and goes only to CARTO, in the tile URLs.
const ALMACEN_LLAVE_CARTO = 'traza.cartoKey';
// The key is spliced into a URL, so only URL-unreserved characters get through
// (letters, digits, - . _ ~): that covers hex, UUID and JWT-style tokens, and
// leaves nothing for encodeURIComponent to change or for a template to read.
const FORMATO_LLAVE_CARTO = /^[A-Za-z0-9._~-]{8,2048}$/;

function urlTeselasCarto(estilo, llave) {
    const base = `https://{s}.basemaps.cartocdn.com/${estilo}/{z}/{x}/{y}{r}.png`;
    return llave ? `${base}?key=${encodeURIComponent(llave)}` : base;
}

// Read and written in try/catch: in a private window or with site data blocked
// the accessor itself THROWS, and the map must load all the same.
function leerLlaveCarto() {
    try {
        const llave = localStorage.getItem(ALMACEN_LLAVE_CARTO);
        return llave && FORMATO_LLAVE_CARTO.test(llave) ? llave : null;
    } catch {
        return null;
    }
}

let llaveCarto = leerLlaveCarto();

// CartoDB Dark Matter without labels: under the 0.65 choropleth fill the
// street labels would be noise, not text.
const darkBaseLayer = L.tileLayer(urlTeselasCarto('dark_nolabels', llaveCarto), {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// CartoDB Positron, also without labels, so switching base changes the theme
// and nothing else.
const lightBaseLayer = L.tileLayer(urlTeselasCarto('light_nolabels', llaveCarto), {
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

// Both styles take the key, so switching base never drops back to the
// watermark. setUrl redraws the layer on the map and only stores the URL on
// the other one.
function aplicarLlaveCarto(llave) {
    llaveCarto = llave;
    darkBaseLayer.setUrl(urlTeselasCarto('dark_nolabels', llave));
    lightBaseLayer.setUrl(urlTeselasCarto('light_nolabels', llave));
}

const formLlaveCarto = document.getElementById('carto-key-form');
const campoLlaveCarto = document.getElementById('carto-key');
const estadoLlaveCarto = document.getElementById('carto-key-status');

// Only the last four characters are ever shown back: enough to tell two keys
// apart, not enough to copy one off a shared screen.
const finDeLlave = llave => `…${llave.slice(-4)}`;

function describirLlaveCarto() {
    estadoLlaveCarto.textContent = llaveCarto
        ? `Usando tu llave guardada en este navegador (termina en ${finDeLlave(llaveCarto)}).`
        : 'Sin llave: el mapa base se ve con la marca de agua de CARTO.';
}

formLlaveCarto.addEventListener('submit', e => {
    e.preventDefault();
    const llave = campoLlaveCarto.value.trim();
    if (!FORMATO_LLAVE_CARTO.test(llave)) {
        estadoLlaveCarto.textContent = llave
            ? 'Eso no parece una llave de CARTO: lleva caracteres que una llave no usa. No se guardó.'
            : 'Pega tu llave en el campo antes de guardar.';
        return;
    }
    aplicarLlaveCarto(llave);
    campoLlaveCarto.value = '';
    let guardada = true;
    try {
        localStorage.setItem(ALMACEN_LLAVE_CARTO, llave);
    } catch {
        guardada = false;
    }
    estadoLlaveCarto.textContent = (guardada
        ? `Llave guardada y aplicada (termina en ${finDeLlave(llave)}).`
        : `Llave aplicada solo a esta visita: este navegador no permite guardarla (termina en ${finDeLlave(llave)}).`)
        + ' Si el fondo sigue con la marca de agua, CARTO no la aceptó.';
});

document.getElementById('carto-key-clear').addEventListener('click', () => {
    try {
        localStorage.removeItem(ALMACEN_LLAVE_CARTO);
    } catch {
        // Nothing stored to remove; the key in use is dropped below anyway.
    }
    aplicarLlaveCarto(null);
    campoLlaveCarto.value = '';
    estadoLlaveCarto.textContent = 'Llave quitada de este navegador. El mapa base vuelve a la marca de agua.';
});

describirLlaveCarto();

// Detail sidebar: open/close
const detailsSidebar = document.getElementById('details-sidebar');

// The card stays in the DOM when closed (it slides out and fades), so `inert`
// is what takes its controls out of the tab order. It is set with the class,
// not after the animation.
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
    // The outline marks what the card describes, so closing the card clears it.
    limpiarSeleccion();
});

// --- Shared choropleth and legend utilities ---

// Escapes text before interpolating it into innerHTML templates.
// Contract: HTML text nodes and QUOTED attribute values only. It is not enough
// for an unquoted attribute, a URL (`href`/`src`) or a CSS context. Legend
// swatches put a color in `data-swatch`, which is assigned to
// `style.background`: that value must stay a hardcoded palette constant.
function esc(valor) {
    return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* Map color budget. Each family means one thing:
   · brick-red    → DANGER   (risk layers)
   · amber-cream  → VALUE    (investment index, cadastral value)
   · teal         → COVERAGE (basic services)
   Ramps are sequential and share one direction: light = low, dark = high, so
   they read in grayscale and with deuteranopia. The dark end stays saturated
   so it does not merge with the near-black basemap (#0b0c0e). */

// Index 0 is the lowest value (lightest tone). Services and Investment use
// different hues because both can be on over the same AGEBs.
const RAMPA_SERVICIOS = ['#7fd4c4', '#35a396', '#2a7d75', '#235a58', '#1d3a3c'];
const RAMPA_INVERSION = ['#f2d79c', '#d29b33', '#a87c27', '#7d5c22', '#4a3a24'];

// Cadastral value shares the amber ramp: color is assigned by meaning (value),
// not by layer. The legend warns when two active layers share a ramp.
const RAMPA_CATASTRO = RAMPA_INVERSION;

// The breaks below read their colors from that ramp by index.

// Fixed pesos/m² breaks, not quantiles: there are only 14 distinct values (one
// per terrain class), and quantiles would cut between identical figures.
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

/* Breaks are computed by QUANTILES over the real data. Both indices are skewed
   upward (median 91.7 for services, 86.1 for investment), so fixed steps would
   put ~9 of 10 AGEBs in one class. The color therefore shows relative position
   within the city, not an absolute score.

   `piso` turns the lowest class into an ABSOLUTE band and runs the quantiles
   over the rest, for a thin tail that quantiles cannot separate (4% of the
   sectors span 0-80% of services coverage). Pass a floor only where the
   threshold means something in the world, such as a coverage percentage. */
function escalonesPorCuantiles(valores, rampa, sufijo = '', piso = null) {
    const datos = valores
        .filter(v => v !== null && v !== undefined && !Number.isNaN(v))
        .sort((a, b) => a - b);
    if (datos.length === 0) return [];

    const fmt = v => v.toFixed(1) + sufijo;
    // A floor nothing falls below -- or that everything falls below -- would
    // produce an empty class, so it simply is not applied.
    const usaPiso = piso !== null && datos[0] < piso && datos[datos.length - 1] >= piso;
    const escalables = usaPiso ? datos.filter(v => v >= piso) : datos;
    const nClases = usaPiso ? rampa.length - 1 : rampa.length;
    const cuantil = p => escalables[Math.min(escalables.length - 1, Math.floor(p * escalables.length))];

    const escalones = [];
    for (let i = nClases - 1; i >= 0; i--) {
        // With a floor, the bottom quantile class starts AT the floor, so the bands
        // in the legend stay contiguous.
        const minimo = i === 0 ? (usaPiso ? piso : escalables[0]) : cuantil(i / nClases);
        const maximo = i === nClases - 1
            ? escalables[escalables.length - 1]
            : cuantil((i + 1) / nClases);
        // If two breaks coincide (many repeated values) the class
        // would be empty; skip it instead of showing a dead color
        // in the legend.
        if (escalones.length && minimo >= escalones[escalones.length - 1].minimo) continue;
        // Sectors per class, counted the way crearFuncionColor assigns them: closed
        // below and open above, except for the top class.
        const esLaMasAlta = i === nClases - 1;
        const conteo = escalables.filter(
            v => v >= minimo && (esLaMasAlta ? v <= maximo : v < maximo)).length;
        escalones.push({
            minimo,
            color: rampa[usaPiso ? i + 1 : i],
            conteo,
            etiqueta: `${fmt(minimo)} - ${fmt(maximo)}`
        });
    }
    if (usaPiso) {
        // The global minimum on purpose: crearFuncionColor walks the classes
        // from the top and takes the first whose minimum the value clears, so
        // this one has to be the catch-all at the bottom.
        escalones.push({
            minimo: datos[0],
            absoluto: true,
            color: rampa[0],
            conteo: datos.length - escalables.length,
            etiqueta: `Menos de ${fmt(piso)}`
        });
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
        // Same zoom scaling as the choropleths.
        weight: pesoBorde(),
        // Opaque and chosen per basemap: measured 3.80:1 over the dark one and
        // 5.18:1 over the light one.
        color: colorBorde(),
        opacity: 1,
        fillOpacity: 0.6
    });
}

// Short layer name for each help disclosure: several legends can be open at
// once, and the summary is what a screen reader announces.
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
        indice: 'Es la única capa de riesgo que penaliza el Índice de Inversión.',
        // Measured caveat (DATOS.md §2.4; §3.8 for the cause), in two halves: the
        // short one is pinned next to the ramp, the episode has its own disclosure.
        advertencia: {
            lead: 'La ausencia de zona marcada no es evidencia de ausencia de inundación.',
            cuerpo: 'Esta capa es solo la inundación pluvial: el desbordamiento de arroyos va en otro capítulo del Atlas que aquí no se publica. En julio de 2025 se inundaron colonias que esta capa deja limpias.'
        },
        limitacion: {
            resumen: '¿Por qué esta capa deja limpias colonias que sí se inundaron?',
            parrafos: [
                'En julio de 2025 se inundaron colonias que este mismo Atlas 2024 clasifica en sus niveles más bajos: Omega llegó a 1.30 m de agua y en esta capa no tiene ni una zona marcada; Terranova, con 1 m, aparece solo como «Bajo» en el 13% de su superficie.',
                'Ninguna de las 16 colonias reportadas alcanza un solo metro clasificado «Alto» ni «Muy alto». Y como se omite «Muy bajo», una colonia clasificada así se dibuja completamente limpia — que es exactamente lo que le ocurre a Omega.',
                'Esto establece que la clasificación publicada subrepresenta inundaciones ocurridas en lugares concretos, y el Atlas mismo explica buena parte de por qué: modela el desbordamiento de arroyos en un capítulo aparte, «Inundaciones fluviales», que clasifica por tirante de agua y corre periodos de retorno desde 5 años — el escenario más frecuente. Lo que se publica en esta capa es el capítulo pluvial y de encharcamientos.',
                'Dos de las colonias inundadas están sobre el Arroyo del Pueblo o junto a él — Nazario Ortiz Garza a 0 m del cauce mapeado por INEGI y Omega a 417 m —, y es una de las corrientes que ese otro capítulo modela; el Atlas atribuye estos desastres a «la invasión y alteración de los cauces». Country Club y Terranova, a 2 km o más del arroyo con nombre más cercano, no quedan explicadas por esta vía.',
                'Episodio reportado por Vanguardia el 24 de julio de 2025; el cruce contra esta capa y la lectura de los documentos del Atlas están documentados en la bitácora de datos del proyecto.'
            ]
        }
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

// Each guard checks exactly the fields its own block renders, so a
// half-filled entry renders no block instead of throwing.
function limitacionDeRiesgo(clave) {
    const ayuda = AYUDA_RIESGO[clave];
    const lim = ayuda && ayuda.limitacion;
    return lim && typeof lim.resumen === 'string' && lim.resumen
        && Array.isArray(lim.parrafos) && lim.parrafos.length ? lim : null;
}

function advertenciaDeRiesgo(clave) {
    const ayuda = AYUDA_RIESGO[clave];
    const adv = ayuda && ayuda.advertencia;
    return adv && adv.lead && adv.cuerpo ? adv : null;
}

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
    // Only a layer whose blank areas were measured against a real event has this.
    const lim = limitacionDeRiesgo(clave);
    const limitacion = lim
        ? `<details class="legend-help">
               <summary>${esc(lim.resumen)}</summary>
               <div class="legend-help-body">
                   <div class="help-caveat">
                       ${lim.parrafos.map(p => `<p>${esc(p)}</p>`).join('')}
                   </div>
               </div>
           </details>`
        : '';
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
        ${limitacion}
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
    // Sits next to the swatches, not inside the collapsed help, because the
    // reader it is for is reading the ramp to decide whether a zone is clear.
    const adv = advertenciaDeRiesgo(clave);
    const aviso = adv
        ? `<p class="legend-caveat"><strong>${esc(adv.lead)}</strong> ${esc(adv.cuerpo)}</p>`
        : '';
    return `<p class="legend-title">${esc(titulo)}</p>${filas}${aviso}${src}${htmlAyudaRiesgo(clave, conteos)}`;
}

// Pre-built legend HTML per risk layer (filled on load).
const leyendasRiesgo = { inundacion: null, deslizamientos: null, quimico: null };

// --- Locate the colonia of a point (point-in-polygon) ----------------
// The IMPLAN risk layers carry no zone name, so a click is located inside
// the AGEBs (which do have COLONIA) by ray casting.

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
        // With no breaks there is no scale to apply (a whole layer without data).
        if (escalones.length === 0) return COLOR_SIN_DATO;
        const escalon = escalones.find(e => valor >= e.minimo);
        return escalon ? escalon.color : escalones[escalones.length - 1].color;
    };
}

/* Stroke weight is in SCREEN pixels, so it does not shrink with the map.
   Measured on the real AGEBs, at weight 1 the outline takes this share of a
   sector's pixels: z13 12%, z12 22%, z11 36%, z10 53%, z9 69%. pesoBorde()
   thins it with zoom to hold it near 12-18%, and removes it below z11. */
// Border color depends on the basemap. Swept against the 16 fills on the map:
// white clears 3:1 over the dark basemap but lands at 1.26:1 over the light
// one, where #1a1a1a is 4.03:1 at worst.
const BORDE_POR_TEMA = { oscuro: '#ffffff', claro: '#1a1a1a' };
let temaBase = 'oscuro';

function colorBorde() {
    return BORDE_POR_TEMA[temaBase];
}

function pesoBorde() {
    const z = map.getZoom();
    if (z >= 13) return 1;
    if (z >= 12) return 0.6;
    if (z >= 11) return 0.4;
    return 0;
}

function crearEstiloCapa(campoValor, funcionColor) {
    return feature => {
        const valor = feature.properties[campoValor];
        return {
            fillColor: funcionColor(valor),
            weight: pesoBorde(),
            // Opaque on purpose: a translucent border blends toward the fill under it
            // and vanishes against the light end of the ramps (2.47:1 at 0.75 alpha).
            color: colorBorde(),
            opacity: 1,
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
    // Averaged over the quantile classes only: the absolute floor class is not
    // the same size as the others.
    const porCuantil = escalones.filter(e => !e.absoluto);
    const piso = escalones.find(e => e.absoluto);
    const porClase = porCuantil.length ? Math.round(
        porCuantil.reduce((n, e) => n + (e.conteo || 0), 0) / porCuantil.length) : 0;
    const reparto = porClase
        ? `Cada una de esas clases agrupa aproximadamente el mismo número de sectores (~${porClase}).`
        : 'Cada una de esas clases agrupa aproximadamente el mismo número de sectores.';
    // Stated because it is the one class whose boundary does NOT move with the
    // data, which is the opposite of what the paragraph above promises.
    const notaPiso = piso
        ? `<p><strong>La clase más baja es la excepción:</strong> «${esc(piso.etiqueta)}» es un
           <em>corte absoluto</em>, no un cuantil, y no se mueve aunque cambien los datos.
           Existe porque la cola baja es muy delgada — ${piso.conteo} de ${escalones.reduce((n, e) => n + (e.conteo || 0), 0)}
           sectores — y por cuantiles quedaba junta con sectores de cobertura muy superior.</p>`
        : '';
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
                ${notaPiso}
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

// Legend registry per layer: every active layer gets its own block.
const SIN_DATO_CONTEO = { servicios: 0, inversion: 0 };

const LEYENDAS = {
    servicios: () => htmlLeyenda('Índice de Servicios Básicos', ESCALONES_SERVICIOS, SIN_DATO_CONTEO.servicios, 'servicios'),
    inversion: () => htmlLeyenda('Índice de Inversión Inmobiliaria', ESCALONES_INVERSION, SIN_DATO_CONTEO.inversion, 'inversion'),
    inundacion: () => leyendasRiesgo.inundacion || '<p class="empty-legend">Cargando…</p>',
    deslizamientos: () => leyendasRiesgo.deslizamientos || '<p class="empty-legend">Cargando…</p>',
    quimico: () => leyendasRiesgo.quimico || '<p class="empty-legend">Cargando…</p>',
    // Replaced by cargarCapaCatastro once the lookup arrives, since its class
    // counts are only known then.
    catastro: () => '<p class="empty-legend">Cargando…</p>',
    // Same: replaced by cargarCapaCauces with the orders and years it found.
    cauces: () => '<p class="empty-legend">Cargando…</p>'
};

// Which risk layers share the single-hue brick ramp: their swatches are
// colored by LEVEL, not by layer, so two risk legends on screen show the
// same color meaning two different things.
const CLAVES_RIESGO = new Set(['inundacion', 'deslizamientos', 'quimico']);

const capasActivas = new Set();

// Legend order is the panel order, read off the DOM. Activation order would
// move the help on every toggle (WCAG 2.2 SC 3.2.6 Consistent Help).
const checkboxPorClave = new Map();

function registrarClaveDeCapa(clave, checkbox) {
    checkboxPorClave.set(clave, checkbox);
}

function ordenDePanel(claves) {
    const enPanel = Array.from(document.querySelectorAll('.layer-control input[type="checkbox"]'));
    return claves.slice().sort((a, b) =>
        enPanel.indexOf(checkboxPorClave.get(a)) - enPanel.indexOf(checkboxPorClave.get(b)));
}

// A layer's family is read off the group that encloses its switch in the
// markup, so regrouping index.html regroups the legend.
function familiaDeCapa(clave) {
    const checkbox = checkboxPorClave.get(clave);
    const grupo = checkbox && checkbox.closest('.layer-group');
    if (!grupo) return null;
    const titulo = grupo.querySelector('.layer-group-title');
    if (!titulo) return null;
    // Keyed by the heading's id, the one aria-labelledby already points at.
    return { id: titulo.id, titulo: titulo.textContent.trim() };
}

// Groups the already panel-ordered keys, keeping that order both between
// families and inside each one. A layer whose group is missing from the markup
// still gets a block, in an unnamed group, rather than vanishing from the
// legend while it is painted on the map.
function agruparPorFamilia(claves) {
    const grupos = [];
    const porId = new Map();
    for (const clave of claves) {
        const familia = familiaDeCapa(clave) || { id: '', titulo: '' };
        let grupo = porId.get(familia.id);
        if (!grupo) {
            grupo = { id: familia.id, titulo: familia.titulo, claves: [] };
            porId.set(familia.id, grupo);
            grupos.push(grupo);
        }
        grupo.claves.push(clave);
    }
    return grupos;
}

// The legend is re-rendered on every toggle, so the open help panes are read
// off the DOM first and restored afterwards.
function ayudasAbiertas() {
    return new Set(Array.from(document.querySelectorAll('#legend-container .legend-block'))
        .filter(bloque => {
            const ayuda = bloque.querySelector('details');
            return ayuda && ayuda.open;
        })
        .map(bloque => bloque.dataset.capa));
}

// Same for the family sections the reader had folded.
function gruposPlegados() {
    return new Set(Array.from(document.querySelectorAll('#legend-container .legend-group'))
        .filter(grupo => !grupo.open)
        .map(grupo => grupo.dataset.grupo));
}

function actualizarLeyenda() {
    const contenedor = document.getElementById('legend-container');
    if (capasActivas.size === 0) {
        contenedor.innerHTML = '<p class="empty-legend">Activa o haz clic en una zona para ver los detalles.</p>';
        return;
    }
    const abiertas = ayudasAbiertas();
    const plegados = gruposPlegados();
    const claves = ordenDePanel(Array.from(capasActivas));

    // Counted over EVERY active layer, not per family: two brick ramps on screen
    // show the same swatch meaning two different things, however the panel
    // groups them.
    const nRiesgo = claves.filter(k => CLAVES_RIESGO.has(k)).length;
    const avisoRiesgo = nRiesgo > 1
        ? `<p class="legend-note">${nRiesgo} capas de riesgo activas. Cada bloque explica la suya:
           los colores se repiten entre capas, y un «Medio» de una no equivale al «Medio» de otra.</p>`
        : '';
    // Placed inside the first family that holds a risk layer, and emitted once.
    let avisoPendiente = avisoRiesgo;

    // The legend mirrors the panel's grouping, and each family folds as a unit.
    contenedor.innerHTML = agruparPorFamilia(claves).map(grupo => {
        let aviso = '';
        if (avisoPendiente && grupo.claves.some(k => CLAVES_RIESGO.has(k))) {
            aviso = avisoPendiente;
            avisoPendiente = '';
        }
        const bloques = grupo.claves.map(clave =>
            `<div class="legend-block" data-capa="${esc(clave)}">${LEYENDAS[clave]()}</div>`).join('');
        if (!grupo.titulo) return aviso + bloques;
        const abierto = plegados.has(grupo.id) ? '' : ' open';
        return `
            <details class="legend-group" data-grupo="${esc(grupo.id)}"${abierto}>
                <summary>${esc(grupo.titulo)} <span class="legend-group-count">${grupo.claves.length}</span></summary>
                <div class="legend-group-body">${aviso}${bloques}</div>
            </details>`;
    }).join('');

    // Each swatch carries its color in data-swatch and gets it through the CSSOM:
    // a style attribute would need 'unsafe-inline' in the CSP. Only a hex literal
    // is ever assigned, so a computed value leaves the swatch uncolored.
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
    elevarCapasDeLinea();
    actualizarLeyenda();
}

function marcarCapaInactiva(clave) {
    capasActivas.delete(clave);
    // With no layer left on the map the outline marks nothing.
    if (capasActivas.size === 0) limpiarSeleccion();
    actualizarLeyenda();
}

// --- Layer availability by visible area ------------------------------
// Outside a layer's coverage its toggle is disabled and explained. Coverage
// comes from the bbox of the loaded GeoJSON (capa.getBounds()), never from a
// hardcoded rectangle.
const capasEnVista = [];

function registrarCapaEnVista(checkbox, capa) {
    const control = checkbox.closest('.layer-control');
    const statusEl = document.createElement('p');
    statusEl.className = 'layer-status';
    statusEl.id = `layer-status-${checkbox.id}`;
    statusEl.textContent = 'Sin datos en la zona visible del mapa.';
    control.appendChild(statusEl);
    // aria-disabled, not the native attribute, keeps the switch reachable and
    // announced; this guard is what stops the toggle, for pointer and space bar.
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

// The style functions read pesoBorde() when Leaflet calls them, so after a
// zoom the layers are told to ask again. The repaint is skipped when the
// weight did not change.
let pesoBordeAplicado = null;
map.on('zoomend', () => {
    const peso = pesoBorde();
    if (peso === pesoBordeAplicado) return;
    pesoBordeAplicado = peso;
    for (const { capa } of capasEnVista) {
        if (capa && typeof capa.resetStyle === 'function') capa.resetStyle();
    }
});

// Same for colorBorde() when the basemap changes. Compared against the layer
// object, not `e.name`, which is UI text.
map.on('baselayerchange', e => {
    temaBase = e.layer === lightBaseLayer ? 'claro' : 'oscuro';
    for (const { capa } of capasEnVista) {
        if (capa && typeof capa.resetStyle === 'function') capa.resetStyle();
    }
});

// A missing value is shown as a dash, not as 0: "I don't know" and "it
// is zero" are different statements and the map must not confuse them.
const SIN_VALOR = '—';
const formatoEntero = valor => sinDato(valor) ? SIN_VALOR : Number(valor).toLocaleString('es-MX');
const formatoPct = valor => sinDato(valor) ? SIN_VALOR : `${Number(valor).toFixed(1)}%`;
const formatoIndice = valor => sinDato(valor) ? SIN_VALOR : Number(valor).toFixed(1);

// Outside the IMPLAN Atlas there is no flood penalty, so no index is published.
// Tested against `false`, not for falsiness: an older cached GeoJSON has no
// such field, and `undefined` must not read as "not assessed".
function htmlSinEvaluacionDeRiesgo(props) {
    return props.RIESGO_EVALUADO === false
        ? `<p class="detail-source">Sin Índice de Inversión: este sector queda fuera del Atlas
           de Riesgos del IMPLAN, que solo cubre el municipio de Saltillo, así que
           <strong>el 30% del peso del índice nunca se midió aquí</strong>. No significa que no
           haya riesgo de inundación, sino que nadie lo ha evaluado — y publicar el número sin
           ese término lo dejaría por encima de sectores que sí pagaron la penalización.</p>`
        : '';
}

// Note explaining why an AGEB has no index (no dwellings, figures
// masked for confidentiality, or absent from the Census).
function htmlMotivoSinDato(props) {
    return props.MOTIVO_SIN_DATO
        ? `<p class="detail-source">Sin dato de servicios: ${esc(props.MOTIVO_SIN_DATO)}.</p>`
        : '';
}

// When the card is opened from a street search it names the street, and says
// so when the settlement INEGI records for that block front differs from the
// colonia the map assigns to the sector (42.1% of fronts: an AGEB spans
// several settlements and the map keeps the dominant one).
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
        // The card's title is one of them; the others are listed.
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
        ${htmlSinEvaluacionDeRiesgo(props)}
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
                    escalonesPorCuantiles(
                        valores, configEscala.rampa, configEscala.sufijo, configEscala.piso ?? null)
                );
                SIN_DATO_CONTEO[clave] = valores.filter(sinDato).length;
            }

            capa = L.geoJSON(geojson, {
                style: funcionEstilo,
                onEachFeature: (feature, layer) => {
                    layer.on({
                        mouseover: e => e.target.setStyle({ weight: 2, color: colorBorde(), fillOpacity: 0.8 }),
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
            // Counted per level, for the legend help.
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
                        mouseover: e => e.target.setStyle({ weight: 2, color: colorBorde(), fillOpacity: 0.75 }),
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
// Informational layer: it does NOT feed the Investment Index. It has no
// geometry file: data/valor_catastral.json is a lookup keyed by AGEB, and the
// polygons are the ones the services layer already fetched.
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
        // "No row in the tables" and "municipality not covered" are different facts.
        const motivo = String(props.NOM_MUN || '').toUpperCase() === 'SALTILLO'
            ? `La colonia <strong>${esc(props.COLONIA || 'de este sector')}</strong> no aparece
               en las tablas de valores del municipio. Puede ser un desarrollo posterior a la
               edición vigente, un nombre registrado de otra forma, o suelo no residencial.`
            : `Las tablas de valores son del <strong>municipio de Saltillo</strong>, y este
               sector está en <strong>${esc(props.NOM_MUN || 'otro municipio')}</strong>.`;
        cuerpo = `<p class="detail-note">Sin valor catastral publicado. ${motivo}</p>`;
    } else {
        // Says which of the two matching rules paired the names.
        const motivoAlias = dato.via === 'espacios'
            ? 'escrito junto o separado distinto'
            : 'mismas palabras, otro orden';
        const alias = dato.nombre_catastro
            ? `<p class="detail-note">El catastro registra esta colonia como
               <strong>${esc(dato.nombre_catastro)}</strong> (${motivoAlias}).</p>`
            : '';
        // `dato.valor` can be null: a class present in the colonia table but missing
        // from the value table exports that way.
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

// Fetched once and shared: the layer and the criteria search both read it, and
// neither should depend on the other having been switched on.
const catastroListo = fetch('data/valor_catastral.json', { cache: 'no-cache' }).then(r => r.json());

function cargarCapaCatastro(checkbox) {
    let capa = null;
    registrarClaveDeCapa('catastro', checkbox);

    // Needs both the lookup and the AGEB polygons, which arrive from a
    // different request; whichever lands second starts the work.
    Promise.all([
        catastroListo,
        agebsListos
    ]).then(([catastro, geojson]) => {
        catastroMeta = { fuente: catastro.fuente, edicion: catastro.edicion };

        const conteos = {};
        let sinDato = 0;
        const features = geojson.features.map(f => {
            // hasOwn, not a truthiness check: `sectores` comes from JSON.parse, and a key
            // like "constructor" would return an inherited function.
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
                // Same border rule as crearEstiloCapa.
                weight: pesoBorde(), opacity: 1, color: colorBorde(), fillOpacity: 0.65
            }),
            onEachFeature: (feature, layer) => {
                layer.on({
                    mouseover: e => e.target.setStyle({ weight: 2, color: colorBorde(), fillOpacity: 0.8 }),
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

// --- Stream courses (INEGI Red Hidrográfica 1:50 000) ----------------
// Context, not risk: drawn as INEGI mapped it in 1998-2008, never classified
// and kept out of every index (DATOS.md §3.8).
//
// Cased like the selection outline, because no single color stays visible
// over every fill: the core reads at ~4.8:1 against its casing, 4.9:1 on the
// dark basemap and 3.6-3.9:1 on the light one.
const COLOR_CAUCE = '#3d7fd6';
const CASCO_CAUCE = '#0b0c0e';
// Core width by Strahler order: higher order, more water gathered upstream.
const ANCHO_CAUCE = orden => (orden >= 6 ? 3.5 : 2);

function htmlLeyendaCauces(conteos, anios, fuente, edicion) {
    const filas = Array.from(conteos.keys()).sort((a, b) => a - b).map(orden => `
        <div class="legend-row">
            <span class="legend-swatch legend-line legend-line-${orden >= 6 ? 'gruesa' : 'fina'}" data-swatch="${COLOR_CAUCE}"></span>
            <span>Orden ${orden} — ${conteos.get(orden).toLocaleString('es-MX')} tramos</span>
        </div>
    `).join('');
    const conFechas = Number.isFinite(anios.min);
    const periodo = !conFechas ? '' : anios.min === anios.max ? `${anios.min}` : `${anios.min} y ${anios.max}`;
    const trazados = conFechas ? `Trazados entre ${periodo}` : 'Fecha de captura no disponible';
    const capturadas = conFechas ? `se capturaron entre ${periodo}` : 'son de la captura del INEGI';
    return `
        <p class="legend-title">Cauces mapeados (INEGI)</p>
        ${filas}
        <p class="legend-source">${esc(trazados)}; no es una capa de riesgo y no entra en ningún índice.
           Fuente: ${esc(fuente)} · ${esc(edicion)}.</p>
        <details class="legend-help">
            <summary>¿Qué muestran los Cauces?</summary>
            <div class="legend-help-body">
                <p><strong>Qué son:</strong> las corrientes que INEGI trazó en su red hidrográfica.
                   Dentro de la mancha urbana casi todas son intermitentes: llevan agua solo cuando llueve.</p>
                <p><strong>Por qué solo orden 5 y mayor:</strong> el orden de Strahler mide la jerarquía de un
                   cauce — dos de orden 4 que se unen forman uno de orden 5. El Atlas de Riesgos 2014 del
                   municipio modeló el desbordamiento justo en los cauces de orden 5, 6 y 7; aquí se usa el
                   mismo corte.</p>
                <p><strong>Por qué importa la fecha:</strong> las líneas ${esc(capturadas)},
                   antes de buena parte del crecimiento actual. Donde una cruza hoy calles y casas, el cauce
                   puede estar entubado, desviado o construido encima: el mapa muestra por dónde corría el agua,
                   no por dónde corre hoy.</p>
                <p><strong>Lo que no es:</strong> no clasifica riesgo ni modela inundación. Estar cerca de un
                   cauce no prueba que una zona se inunde, ni lo contrario. Sirve para leer junto a la capa de
                   inundación, que es solo pluvial y deja fuera el desbordamiento de arroyos.</p>
            </div>
        </details>
    `;
}

function mostrarDetalleCauce(props) {
    document.getElementById('sector-title').textContent = `Cauce de orden ${props.ORDEN}`;
    document.getElementById('sector-info').innerHTML = `
        <p class="detail-row"><span>Condición</span><strong>${esc(props.CONDICION)}</strong></p>
        <p class="detail-row"><span>Capturado en</span><strong>${Number.isInteger(props.ANIO_CAPTURA) ? props.ANIO_CAPTURA : SIN_VALOR}</strong></p>
        <p class="detail-note">Es la línea que INEGI cartografió ese año. Hoy el cauce puede estar
           entubado, desviado o construido encima, y su cercanía no indica riesgo por sí sola.</p>
        <p class="detail-source">Fuente: ${esc(props.FUENTE)} · ${esc(props.FECHA)}.</p>
    `;
    abrirFicha();
}

// A polygon layer switched on later is brought to the front and would paint
// over the lines, so they are lifted back above it: the search's outlines last.
function elevarCapasDeLinea() {
    for (const capa of [capaCauces, capaCoincidencias]) {
        if (capa && map.hasLayer(capa)) capa.bringToFront();
    }
}

// Drawn in the default overlay pane, sharing the polygons' canvas. A pane of
// its own would get a map-sized canvas that takes every click meant for the
// sectors; one canvas hit-tests top-down and falls through to the polygon.
let capaCauces = null;

function cargarCapaCauces(checkbox) {
    let capa = null;
    registrarClaveDeCapa('cauces', checkbox);

    fetch('data/cauces_inegi.geojson', { cache: 'no-cache' })
        .then(respuesta => respuesta.json())
        .then(geojson => {
            const conteos = new Map();
            const anios = { min: Infinity, max: -Infinity };
            for (const f of geojson.features) {
                const p = f.properties;
                // The order reaches innerHTML and a class name, so only an
                // integer is let through to either.
                if (!Number.isInteger(p.ORDEN)) continue;
                conteos.set(p.ORDEN, (conteos.get(p.ORDEN) || 0) + 1);
                // A non-integer year is left out of the range.
                if (Number.isInteger(p.ANIO_CAPTURA)) {
                    anios.min = Math.min(anios.min, p.ANIO_CAPTURA);
                    anios.max = Math.max(anios.max, p.ANIO_CAPTURA);
                }
            }
            const p0 = geojson.features.length ? geojson.features[0].properties : {};
            LEYENDAS.cauces = () => htmlLeyendaCauces(conteos, anios, p0.FUENTE, p0.FECHA);

            // The casing is the interactive half: it is the wider of the two, so
            // a thin channel is not a pixel-perfect click target. The core on top
            // lets pointer events through to it.
            let casco = null;
            casco = L.geoJSON(geojson, {
                style: f => ({ color: CASCO_CAUCE, weight: ANCHO_CAUCE(f.properties.ORDEN) + 3, opacity: 1 }),
                onEachFeature: (feature, layer) => {
                    layer.on({
                        mouseover: e => e.target.setStyle({ weight: ANCHO_CAUCE(feature.properties.ORDEN) + 6 }),
                        mouseout: e => casco.resetStyle(e.target),
                        click: e => {
                            resaltarGeometrias([feature.geometry]);
                            mostrarDetalleCauce(feature.properties);
                        }
                    });
                }
            });
            const nucleo = L.geoJSON(geojson, {
                interactive: false,
                style: f => ({ color: COLOR_CAUCE, weight: ANCHO_CAUCE(f.properties.ORDEN), opacity: 1 })
            });
            capa = L.featureGroup([casco, nucleo]);
            capaCauces = capa;

            if (checkbox.checked) {
                capa.addTo(map);
                marcarCapaActiva('cauces');
            }
            registrarCapaEnVista(checkbox, capa);
        })
        .catch(error => console.error('Error loading stream courses:', error));

    checkbox.addEventListener('change', () => {
        if (!capa) return;
        if (checkbox.checked) {
            capa.addTo(map);
            capa.bringToFront();
            marcarCapaActiva('cauces');
        } else {
            map.removeLayer(capa);
            marcarCapaInactiva('cauces');
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

// Fold accents and case, and punctuation to a single space: nobody types the
// period in "FRANCISCO I. MADERO".
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
// The index carries no geometry: each zone lists the AGEBs it touches and
// the position comes from the polygons already loaded. It is fetched lazily,
// on the first search.
let indiceCalles = null;
let cargaCalles = null;

// Shape of the zone tuples this parser understands. Must match
// FORMATO_INDICE_CALLES in scripts/process_data.py. A cached older page can
// receive a newer file, so an unknown version is refused instead of parsed.
const FORMATO_INDICE_CALLES = 2;

function cargarIndiceCalles() {
    if (cargaCalles) return cargaCalles;
    // `no-cache` revalidates with the server, as for the map layers.
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
        // One row per street, never per zone: "LUIS ECHEVERRÍA" runs through 64
        // settlements.
        const tipos = new Set(calle.zonas.map(z => z.tipoVia));
        const unica = calle.zonas.length === 1 ? calle.zonas[0] : null;
        encontrados.push({
            pos, clase: 'calle', orden: 1,
            titulo: calle.nombre,
            // Zones are counted as "tramos"; a merged zone with many settlement names
            // shows how many there are instead of listing them.
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
    // Each option has an id so aria-activedescendant can point at it: focus
    // never leaves the input. The kind tag is inside the option so a screen
    // reader announces whether it is a colonia or a street. The name gets its
    // own line because a long settlement label would otherwise squeeze it out.
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

// The selection is a SEPARATE overlay, not a restyle of the clicked feature:
// the risk layers render to a canvas and reset their style on mouseout.
//
// A cased line (dark casing under an amber core) because no single color
// stays visible over every fill: amber alone is 1.10-1.16:1 against the
// second class of each ramp. Core against casing is 7.16:1.
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

// A colonia can cover several AGEBs, the unit every figure is measured on.
// The card lists the sectors and lets one be chosen instead of averaging.
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
    // Paired by position, not by a key round-tripped through the DOM: a lookup
    // that misses would show another sector's figures.
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
    // The polygons are drawn on a canvas and have no DOM node to focus, so the
    // card is the keyboard route to the data.
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

// Reuses the colonia flow: one AGEB goes straight to its figures, several
// show the sector chooser.
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
        // Only commits while the list is open, so Escape cancels.
        if (buscadorSugerencias.hidden) return;
        e.preventDefault();
        const idx = sugerenciaActiva >= 0 ? sugerenciaActiva : 0;
        seleccionarResultado(resultadosFiltrados[idx]);
    } else if (e.key === 'Escape') {
        cerrarSugerencias();
    }
});

// WCAG 2.2 SC 2.4.11 (Focus Not Obscured): closing on focus-out keeps the
// list from covering the control that receives focus next.
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

// --- Find zones by criteria ------------------------------------------
// A deterministic filter over fields already published per AGEB (DATOS.md
// §3.9). Rules:
//  · A sector with no figure for a criterion does NOT match; it is counted
//    apart.
//  · Criteria describe the place, never the people who live there.
//  · Results are not ranked: they are listed by colonia name.

// Radius of the proximity scores, RADIO_MAX_KM in process_data.py: each
// SCORE_* is 100 * (1 - d / 3 km), clipped at 0. Inverting it gives back the
// straight-line distance exactly, except that a 0 only says "3 km or more".
const RADIO_CERCANIA_KM = 3;

function distanciaKm(score) {
    return sinDato(score) ? null : RADIO_CERCANIA_KM * (1 - score / 100);
}

function formatoDistancia(km) {
    if (km >= RADIO_CERCANIA_KM) return `${RADIO_CERCANIA_KM} km o más`;
    if (km < 1) return `${Math.round(km * 100) * 10} m`;
    return `${Number.isInteger(km) ? km : km.toFixed(1)} km`;
}

const formatoPesos = valor => `$${Number(valor).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Every criterion reads its value through `leer`; null means "no figure".
// The accepted values are declared in `opciones` and the select is generated
// from them. A submitted value that is not declared reads as "any".
const OPCIONES_CERCANIA = [[0.5, 'A 500 m o menos'], [1, 'A 1 km o menos'], [2, 'A 2 km o menos']];

const cercania = (id, campo, etiqueta) => ({
    id, etiqueta, fuente: 'INEGI · DENUE 05_2026',
    opciones: OPCIONES_CERCANIA,
    leer: s => distanciaKm(s.props[campo]),
    cumple: (km, max) => km <= max,
    pide: max => `a ${formatoDistancia(max)} o menos`,
    describir: km => `${formatoDistancia(km)} en línea recta`,
    falta: 'sin dato de cercanía'
});

const CRITERIOS = [
    {
        id: 'servicios', etiqueta: 'Servicios básicos', fuente: 'INEGI · Censo 2020',
        opciones: [[80, 'Índice de 80 o más'], [90, 'Índice de 90 o más'], [95, 'Índice de 95 o más']],
        leer: s => s.props.SERVICIOS_INDEX,
        cumple: (v, min) => v >= min,
        pide: min => `índice de ${min} o más`,
        describir: v => `índice ${formatoIndice(v)}`,
        falta: 'sin dato del Censo'
    },
    {
        id: 'inundacion', etiqueta: 'Inundación pluvial', fuente: 'IMPLAN · Atlas de Riesgos 2024',
        opciones: [['sin-zona', 'Ninguna zona marcada en el sector'], ['baja', 'Exposición baja (5 de 100 o menos)']],
        // Compared against `true`, the same way the investment card tests the
        // flag: only a sector the model is known to have covered has a figure.
        leer: s => (s.props.RIESGO_EVALUADO === true ? s.props.RIESGO_INDEX : null),
        cumple: (v, modo) => (modo === 'sin-zona' ? v === 0 : v <= 5),
        pide: modo => (modo === 'sin-zona' ? 'ninguna zona marcada' : 'exposición de 5 de 100 o menos'),
        describir: v => (v === 0 ? 'ninguna zona marcada' : `exposición ${formatoIndice(v)} de 100`),
        falta: 'fuera del Atlas de Riesgos'
    },
    cercania('escuela', 'SCORE_ESCUELA', 'Escuela más cercana'),
    cercania('salud', 'SCORE_SALUD', 'Salud más cercana'),
    cercania('supermercado', 'SCORE_SUPERMERCADO', 'Supermercado más cercano'),
    {
        id: 'catastro', etiqueta: 'Valor catastral', fuente: 'Tesorería Municipal de Saltillo · 2026',
        // Filled from the published figures once the lookup arrives.
        opciones: [],
        leer: s => (s.catastro ? s.catastro.valor : null),
        cumple: (v, max) => v <= max,
        pide: max => `hasta ${formatoPesos(max)} por m²`,
        describir: (v, s) => `${formatoPesos(v)} por m² · ${s.catastro.clase}`,
        falta: 'sin valor catastral publicado'
    }
];

let anunciarInversion;
const inversionLista = new Promise(resolver => { anunciarInversion = resolver; });

// Sectors the search runs over: geometry, published properties and the
// cadastral figure joined by CVEGEO, built once both files are in.
let sectoresBusqueda = [];
let capaCoincidencias = null;

const formCriterios = document.getElementById('criteria-form');
const estadoCriterios = document.getElementById('criteria-status');

// Municipalities offered, filled from the data like the cadastral options.
let municipiosOfrecidos = [];

function poblarOpciones(select, opciones) {
    for (const [valor, texto] of opciones) select.add(new Option(texto, String(valor)));
}

// The submitted string is looked up among the declared options and the
// declared value is what gets used, never the string parsed.
function valorDeclarado(texto, opciones) {
    const hallada = opciones.find(([valor]) => String(valor) === texto);
    return hallada ? hallada[0] : null;
}

function leerFiltros() {
    const datos = new FormData(formCriterios);
    const municipio = valorDeclarado(String(datos.get('municipio') || ''), municipiosOfrecidos) || '';
    const filtros = {};
    for (const c of CRITERIOS) filtros[c.id] = valorDeclarado(String(datos.get(c.id) || ''), c.opciones);
    return { municipio, filtros };
}

function buscarZonas({ municipio, filtros }) {
    const activos = CRITERIOS.filter(c => filtros[c.id] !== null);
    const enAlcance = sectoresBusqueda.filter(s => !municipio || s.props.NOM_MUN === municipio);
    const coincidencias = [];
    // Sectors that meet every criterion they have a figure for but lack one
    // or more: they are the ones "no data" actually kept out, so they are
    // what gets counted -- not every sector missing a field, most of which
    // fail another criterion anyway.
    let posibles = 0;
    const faltantes = new Map(activos.map(c => [c.id, 0]));
    for (const s of enAlcance) {
        let falla = false;
        const sinFigura = [];
        for (const c of activos) {
            const v = c.leer(s);
            if (sinDato(v)) sinFigura.push(c.id);
            else if (!c.cumple(v, filtros[c.id])) { falla = true; break; }
        }
        if (falla) continue;
        if (sinFigura.length) {
            posibles++;
            for (const id of sinFigura) faltantes.set(id, faltantes.get(id) + 1);
        } else {
            coincidencias.push(s);
        }
    }
    coincidencias.sort((a, b) =>
        String(a.props.COLONIA).localeCompare(String(b.props.COLONIA), 'es')
        || String(a.props.CVEGEO).localeCompare(String(b.props.CVEGEO)));
    return { municipio, filtros, activos, enAlcance: enAlcance.length, coincidencias, posibles, faltantes };
}

// Outlined, not filled, so the layer the reader has on stays readable under
// the result. Cased like the selection and in its amber, but dashed and
// thinner: these are candidates, the solid outline is the one being read.
function dibujarCoincidencias(coincidencias) {
    if (capaCoincidencias) map.removeLayer(capaCoincidencias);
    capaCoincidencias = null;
    if (!coincidencias.length) return;
    const coleccion = {
        type: 'FeatureCollection',
        features: coincidencias.map(s => ({ type: 'Feature', geometry: s.geometria, properties: {} }))
    };
    const contorno = estilo => L.geoJSON(coleccion, { interactive: false, style: { fill: false, ...estilo } });
    capaCoincidencias = L.featureGroup([
        contorno({ color: '#0b0c0e', weight: 4 }),
        contorno({ color: '#c8912f', weight: 1.75, dashArray: '5 4' })
    ]).addTo(map);
    capaCoincidencias.bringToFront();
}

function etiquetaAlcance(municipio) {
    return municipio ? `en ${municipio}` : 'en los tres municipios';
}

function mostrarResultadosCriterios(r, enfocar = null) {
    const n = r.coincidencias.length;
    const pedidos = r.activos.map(c =>
        `<li><span>${esc(c.etiqueta)}</span> ${esc(c.pide(r.filtros[c.id]))}</li>`).join('');
    const faltan = r.activos.filter(c => r.faltantes.get(c.id) > 0)
        .map(c => `${esc(c.falta)} (${r.faltantes.get(c.id).toLocaleString('es-MX')})`);
    const notaFaltantes = r.posibles
        ? `<p class="detail-note">Otros <strong>${r.posibles.toLocaleString('es-MX')}</strong>
               ${r.posibles === 1 ? 'sector cumple' : 'sectores cumplen'} todo lo que sí se sabe de
               ${r.posibles === 1 ? 'él' : 'ellos'}, pero les falta dato: ${faltan.join('; ')}.
               No se cuentan como coincidencias: no tener dato no es cumplir.</p>`
        : '';
    const avisoInundacion = r.filtros.inundacion !== null
        ? `<p class="detail-note detail-note-riesgo"><strong>Sin zona marcada no es sin inundación.</strong>
               La capa es solo pluvial: el desbordamiento de arroyos va en otro capítulo del Atlas que
               aquí no se publica, y en julio de 2025 se inundaron colonias que esta capa deja limpias.</p>`
        : '';
    const lista = n
        ? `<ul class="sector-list">${r.coincidencias.map(s => `
                <li>
                    <button type="button" class="sector-btn">
                        <span class="sector-btn-name">${esc(s.props.COLONIA)}</span>
                        <span class="sector-btn-meta">${esc(s.props.NOM_MUN)} · AGEB ${esc(String(s.props.CVEGEO).slice(-4))}</span>
                    </button>
                </li>`).join('')}</ul>`
        : '<p class="sector-hint">Ningún sector cumple todos los criterios. Prueba relajando alguno.</p>';

    document.getElementById('sector-title').textContent = 'Zonas que cumplen';
    document.getElementById('sector-info').innerHTML = `
        <p class="detail-row"><span>Sectores que cumplen</span><strong>${n.toLocaleString('es-MX')} de ${r.enAlcance.toLocaleString('es-MX')}</strong></p>
        <p class="sector-hint">${esc(etiquetaAlcance(r.municipio))}, con todos estos criterios:</p>
        <ul class="criteria-summary">${pedidos}</ul>
        ${notaFaltantes}
        ${avisoInundacion}
        ${n ? '<h3>Elige un sector para ver por qué coincide</h3><p class="sector-hint">En orden alfabético: no es un ranking. En el mapa, contorno ámbar punteado.</p>' : ''}
        ${lista}
    `;
    // Paired by position, as in the colonia chooser: a key round-tripped
    // through the DOM that missed would show another sector's figures.
    document.getElementById('sector-info').querySelectorAll('.sector-btn').forEach((btn, i) => {
        btn.addEventListener('click', () => mostrarPorQueCoincide(r.coincidencias[i], r, i));
    });
    abrirFicha();
    // Coming back from a sector, focus returns to the button that opened it;
    // replacing the card's markup would otherwise drop it to <body> and send
    // a keyboard user back to the top of the page.
    if (enfocar !== null) {
        const btn = document.getElementById('sector-info').querySelectorAll('.sector-btn')[enfocar];
        if (btn) btn.focus();
    }
}

function mostrarPorQueCoincide(s, r, indice) {
    encuadrarYResaltar([s]);
    const filas = r.activos.map(c => `
        <p class="detail-row"><span>${esc(c.etiqueta)}</span><strong>${esc(c.describir(c.leer(s), s))}</strong></p>
        <p class="criteria-row-src">Se pidió ${esc(c.pide(r.filtros[c.id]))} · ${esc(c.fuente)}</p>
    `).join('');
    const usaCercania = r.activos.some(c => ['escuela', 'salud', 'supermercado'].includes(c.id));
    const notas = [
        usaCercania ? 'Las distancias son en línea recta desde el centro del sector hasta el establecimiento más cercano del DENUE, no por calle.' : '',
        r.filtros.catastro !== null ? 'El valor catastral es la base del predial, asignado a toda la colonia: no es precio de mercado ni avalúo del predio.' : '',
        r.filtros.inundacion !== null ? 'La inundación es solo pluvial: no incluye el desbordamiento de arroyos.' : ''
    ].filter(Boolean).map(t => `<p>${esc(t)}</p>`).join('');

    document.getElementById('sector-title').textContent = s.props.COLONIA;
    document.getElementById('sector-info').innerHTML = `
        <button type="button" class="criteria-back">← Volver a los resultados</button>
        <p class="detail-row"><span>Municipio</span><strong>${esc(s.props.NOM_MUN)}</strong></p>
        <h3>Por qué coincide</h3>
        ${filas}
        ${notas ? `<div class="detail-source">${notas}</div>` : ''}
    `;
    const volver = document.querySelector('#sector-info .criteria-back');
    volver.addEventListener('click', () => {
        limpiarSeleccion();
        mostrarResultadosCriterios(r, indice);
    });
    abrirFicha();
    // The button that was pressed no longer exists, so focus goes to the way back.
    volver.focus();
}

function limpiarCriterios() {
    if (capaCoincidencias) map.removeLayer(capaCoincidencias);
    capaCoincidencias = null;
    estadoCriterios.textContent = '';
}

formCriterios.addEventListener('submit', e => {
    e.preventDefault();
    const pedido = leerFiltros();
    if (!CRITERIOS.some(c => pedido.filtros[c.id] !== null)) {
        estadoCriterios.textContent = 'Elige al menos un criterio.';
        return;
    }
    const r = buscarZonas(pedido);
    dibujarCoincidencias(r.coincidencias);
    estadoCriterios.textContent = `${r.coincidencias.length.toLocaleString('es-MX')} de ${r.enAlcance.toLocaleString('es-MX')} sectores cumplen.`;
    mostrarResultadosCriterios(r);
});

// Closes the card if it belongs to this search (the results or a sector's
// "por qué coincide"), recognised by its markup.
formCriterios.addEventListener('reset', () => {
    limpiarCriterios();
    if (document.querySelector('#sector-info .criteria-summary, #sector-info .criteria-back')) {
        cerrarFicha();
        limpiarSeleccion();
    }
});

Promise.all([inversionLista, catastroListo]).then(([geojson, catastro]) => {
    sectoresBusqueda = geojson.features.filter(f => f.geometry).map(f => ({
        geometria: f.geometry,
        props: f.properties,
        // hasOwn for the same reason as the cadastral layer: a key such as
        // "constructor" would otherwise return an inherited function.
        catastro: Object.hasOwn(catastro.sectores, f.properties.CVEGEO)
            ? catastro.sectores[f.properties.CVEGEO] : null
    }));

    municipiosOfrecidos = [...new Set(sectoresBusqueda.map(s => s.props.NOM_MUN))]
        .sort((a, b) => a.localeCompare(b, 'es')).map(m => [m, m]);
    poblarOpciones(document.getElementById('crit-municipio'), municipiosOfrecidos);
    // One option per cadastral figure published, from the cheapest. Classes are
    // collected per figure: POPULAR (2) and INDUSTRIAL (2) are both 464.45.
    const clases = new Map();
    for (const s of sectoresBusqueda) {
        if (!s.catastro || !Number.isFinite(s.catastro.valor)) continue;
        if (!clases.has(s.catastro.valor)) clases.set(s.catastro.valor, new Set());
        clases.get(s.catastro.valor).add(s.catastro.clase);
    }
    const criterioCatastro = CRITERIOS.find(c => c.id === 'catastro');
    criterioCatastro.opciones = [...clases].sort((a, b) => a[0] - b[0]).map(([valor, nombres]) =>
        [valor, `Hasta ${formatoPesos(valor)} por m² · ${[...nombres].sort().join(' / ')}`]);
    for (const c of CRITERIOS) poblarOpciones(document.getElementById(`crit-${c.id}`), c.opciones);
    document.getElementById('criteria-fieldset').disabled = false;
}).catch(error => console.error('Error preparing the criteria search:', error));

cargarCapaChoropleth({
    archivo: 'data/servicios_basicos.geojson',
    checkbox: document.getElementById('layer-services'),
    clave: 'servicios',
    campoValor: 'SERVICIOS_INDEX',
    configEscala: {
        rampa: RAMPA_SERVICIOS,
        sufijo: '%',
        // Absolute floor, not a quantile: see escalonesPorCuantiles.
        piso: 80,
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
    funcionDetalle: mostrarDetalleInversion,
    // Every field the criteria search filters on is in this file, so it is
    // what the search reads, loaded whether or not the layer is on.
    alCargarGeojson: geojson => anunciarInversion(geojson)
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

// Stream courses (INEGI, 1:50 000). Context only: no index reads it.
cargarCapaCauces(document.getElementById('layer-streams'));

// Backup (ANRI - CONAGUA): the flood layer by Tr=100 severity is kept
// as a raster in data/riesgo_inundacion.png (+_meta.json). To reactivate
// it as an imageOverlay, load meta.bounds and use L.imageOverlay(...).
// IMPLAN is the primary source (local, vector).

console.log("Leaflet initialized successfully.");
