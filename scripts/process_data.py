"""
Traza — Spatial data processing script
--------------------------------------
Phase 2, Task 1: Filter INEGI's AGEB layer to keep only the polygons of the
municipalities of interest (Saltillo, Ramos Arizpe, Arteaga).

The AGEB source is INEGI's product "Información vectorial de localidades
amanzanadas y números exteriores 2023" (NOT the Marco Geoestadístico: that is
just one of its base layers, December 2022 edition). The full provenance of
this and the other datasets is in DATOS.md.

For now, AGEB data is only downloaded for Saltillo. The MUNICIPIOS_AGEB config
is ready so that, as soon as the localities for Ramos Arizpe and Arteaga are
downloaded (same INEGI format: one folder per locality with
conjunto_de_datos/<locality_key>a.shp), it is enough to add their paths here.

Phase 2, Task 2: Process the basic-services data from the 2020 Population and
Housing Census (INEGI, urban AGEB level) and join it to the AGEB polygons by
CVEGEO.

Phase 2, Task 3: Spatial cross of the AGEBs with the flood zones (vector
overlay against the IMPLAN layers, see below). CENAPRED's municipal dataset
was discarded for lacking intra-urban granularity.

Phase 2, Task 4: Export the Basic Services layer as clean, lightweight GeoJSON
in the data/ folder, ready for Leaflet to load directly.

Extra: AGEBs have no colonia name of their own (they are statistical units,
they do not match a colonia 1:1). The name is derived from the "Frente de
manzana" (fm) layer, which does carry the NOMASEN field (settlement name) per
block front: the most frequent NOMASEN among each AGEB's fronts is used as an
approximation of its colonia.

Phase 5, Task 1: Real-Estate Investment Index (formula defined below). The
"Comercios" component is computed from DENUE (schools, healthcare and
supermarkets) as the proximity of each AGEB's centroid to the nearest
establishment of each category. The "Riesgo" component (weight 0.3) is
computed as each AGEB's flood exposure (IMPLAN layers, below) and applied as a
penalty on the base Services+Comercios index.

Phase 4, Task (risk layers): the risk layers come from IMPLAN Saltillo's 2024
Risk Atlas (CARTO SALTILLO platform), downloaded as vector shapefiles
(EPSG:6372):
  - Urban pluvial flood risk (Layer 1).
  - Translational landslide risk (Layer 4, geological).
Each layer carries an intensity level (Muy bajo→Muy alto). The "Muy bajo"
level is discarded (it covers ~90-98% of the area: it is the background with
no informative value and greatly inflates the GeoJSON) and the layer is
dissolved by level for a lightweight file. Being vector, the cross with the
AGEBs (for the Investment Index risk penalty) is a direct spatial overlay,
with no new dependencies.

Backup: CONAGUA's ANRI flood layer is kept (georeferenced PNG raster,
`descargar_raster_inundacion`) as an alternative source; IMPLAN is the primary
source for being local, vector and from 2024.
"""

import json
import re
import unicodedata
import urllib.parse
import urllib.request
import zlib
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

RAW_DATA = Path("raw_data")
PROCESSED_DIR = RAW_DATA / "processed"
DATA_DIR = Path("data")

# Geometry simplification tolerance in degrees (EPSG:4326). ~0.00005° equals
# ~5 m in Saltillo, enough to lighten the GeoJSON without visibly deforming
# the AGEB polygons at the map's zoom levels.
TOLERANCIA_SIMPLIFICACION = 0.00005

CENSO_CSV = (
    RAW_DATA
    / "ageb_mza_urbana_05_cpv2020_csv"
    / "ageb_mza_urbana_05_cpv2020"
    / "conjunto_de_datos"
    / "conjunto_de_datos_ageb_urbana_05_cpv2020.csv"
)

DENUE_CSV = RAW_DATA / "denue_05_csv" / "conjunto_de_datos" / "denue_inegi_05_.csv"

# Urban amenity categories for the "Comercios" component of the Investment
# Index. "escuela" and "salud" are identified by their SCIAN
# sector (the first two digits of codigo_act); "supermercado" has no sector of
# its own in SCIAN, so it is identified by business-activity name.
CATEGORIAS_DENUE = {
    "escuela": lambda df: df["codigo_act"].str.startswith("61"),
    "salud": lambda df: df["codigo_act"].str.startswith("62"),
    "supermercado": lambda df: df["nombre_act"].str.contains("supermercado", case=False, na=False),
}

# Investment Index weights.
PESO_SERVICIOS = 0.4
PESO_COMERCIOS = 0.3
# Flood-risk penalty. Applied as a subtraction on the base
# Services+Comercios index (see calcular_indice_inversion).
PESO_RIESGO = 0.3

# Distance (km) beyond which an establishment no longer adds proximity points.
# 3 km is a reasonable driving-access radius within a city the size of
# Saltillo; it decays linearly to 0 at that point.
RADIO_MAX_KM = 3.0

# Filler values of the NOMASEN field (settlement name) in INEGI's Frente de
# manzana layer. They are not colonia names: "ND" is "no disponible" (its
# TIPOASEN also says "ND") and "NINGUNO" marks fronts with no settlement
# assigned. They must be discarded before computing the most frequent name per
# AGEB: otherwise an AGEB with 5 "NINGUNO" fronts and 4 with a real name ends
# up called "NINGUNO" on the map. Note: not every short value is filler —
# "GIS" is real (Sector GIS, after Grupo Industrial Saltillo).
VALORES_SIN_ASENTAMIENTO = frozenset({"ND", "NINGUNO"})

# Label for an AGEB with no real settlement name. Preferable to showing the
# raw filler value in the map card.
SIN_COLONIA = "SIN NOMBRE REGISTRADO"

# Filler values of NOMVIAL in the same layer. Unlike NOMASEN's, these are not
# only "unknown" markers: "OTRO" and "MANZANA O EDIFICACIÓN CONTIGUA" describe
# what the front faces when it is not a street at all. None is a street name,
# and left in they dominate the index — "OTRO" alone would appear in 401
# settlements, more than any real street in the city.
VALORES_SIN_VIALIDAD = frozenset({"NINGUNO", "OTRO", "MANZANA O EDIFICACIÓN CONTIGUA", "N/A", "ND"})

# TIPOVIAL values that do not denote a street: "RASGO" is a physical feature
# (an arroyo, a railway — this is where names like "MALEZA" come from) and
# "SIN REFERENCIA" has nothing to point at.
TIPOS_NO_VIALIDAD = frozenset({"RASGO", "SIN REFERENCIA"})

# Street -> settlement index consumed by the frontend search. Not a GeoJSON and
# not part of the map layers: it carries no geometry at all (see
# construir_indice_calles) and the browser fetches it lazily, only once the user
# actually searches, so it does not compete with the 5 MB budget SPEC §2 sets
# for the layers.
CALLES_JSON = DATA_DIR / "calles.json"

# Shape of each zone tuple in calles.json. Version 1 was
# [tipo, asentamiento, municipio, cp, agebs]; version 2 turned the settlement
# and the postal code into lists when zones resolving to the same sectors were
# merged. Must match FORMATO_INDICE_CALLES in index.html.
FORMATO_INDICE_CALLES = 2

# Metric CRS (the same as INEGI's vector cartography) used only to compute
# distances in meters; the final output is reprojected to EPSG:4326.
CRS_METRICO = "EPSG:6372"

# --- Flood Risk layer (ANRI - CONAGUA) -------------------------------------
# Public ArcGIS REST service of the Atlas Nacional de Riesgo por Inundación.
# Layer 142 is "Severidad, periodo de retorno 100 años" from the "Saltillo,
# Coahuila" group (Región Noreste). It is a raster: downloaded as a
# georeferenced PNG to use as an imageOverlay in Leaflet.
ANRI_MAPSERVER = (
    "https://rmgir.proyectomesoamerica.org/server/rest/services/"
    "ANRI/RegionNoreste_ANRI/MapServer"
)
ANRI_CAPA_SEVERIDAD_TR100 = 142
ANRI_FUENTE = (
    "CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI), Región Noreste. "
    "Capa: Severidad, periodo de retorno 100 años (Saltillo, Coahuila)."
)
# Margin (in degrees) around the AGEB extent so we don't clip the flood
# channels that enter/leave the urban footprint.
ANRI_MARGEN_GRADOS = 0.03
# PNG height in pixels; the width is computed proportional to the Web Mercator
# extent to keep pixels ~square and the file lightweight.
ANRI_ALTO_PX = 1500

RIESGO_INUNDACION_PNG = DATA_DIR / "riesgo_inundacion.png"
RIESGO_INUNDACION_META = DATA_DIR / "riesgo_inundacion_meta.json"

# --- IMPLAN risk layers (CARTO SALTILLO - 2024 Risk Atlas) ------------------
# Primary source (vector, local, 2024). Shapefiles in EPSG:6372.
IMPLAN_INUNDACION_SHP = (
    RAW_DATA / "Riesgo_por_inundaciones_pluviales3"
    / "Riesgo_por_inundaciones_pluviales3.shp"
)
IMPLAN_DESLIZAMIENTOS_SHP = (
    RAW_DATA / "Riesgo_por_Deslizamientos_traslacionales2"
    / "Riesgo_por_Deslizamientos_traslacionales2.shp"
)
IMPLAN_QUIMICO_SHP = (
    RAW_DATA / "Riesgo_Quimico_tecnologico"
    / "Riesgo_Quimico_tecnologico.shp"
)
IMPLAN_FUENTE = "IMPLAN Saltillo — CARTO SALTILLO, Atlas de Riesgos 2024"
IMPLAN_FECHA_CORTE = "2024"

# Source of the AGEB polygons and of the Frente de manzana layer behind both the
# colonia names and the street index (see DATOS.md §2.1).
INEGI_VECTORIAL_FUENTE = (
    "INEGI — Información vectorial de localidades amanzanadas y números "
    "exteriores 2023"
)
INEGI_VECTORIAL_FECHA_CORTE = "2023"

# Traffic-light order of intensity and its 0-100 score for the penalty.
NIVELES_INTENSIDAD = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"]
PUNTAJE_INTENSIDAD = {"Muy bajo": 0, "Bajo": 25, "Medio": 50, "Alto": 75, "Muy alto": 100}
# Levels kept in the visible layers and in the penalty. "Muy bajo" is
# discarded (background of ~90-98% of the area, no risk value).
NIVELES_ELEVADOS = ["Bajo", "Medio", "Alto", "Muy alto"]
# Higher threshold for chemical-technological risk: there "Bajo" covers 93% of
# the grid (the model's background, no discriminating value) and, if kept, the
# layer alone would exceed the project's 5 MB limit (6.9 MB measured). With
# Medio+Alto it stays at ~1.2 MB, showing only the genuinely exposed zones.
NIVELES_ELEVADOS_QUIMICO = ["Medio", "Alto", "Muy alto"]

RIESGO_INUNDACION_GEOJSON = DATA_DIR / "riesgo_inundacion.geojson"
RIESGO_DESLIZAMIENTOS_GEOJSON = DATA_DIR / "riesgo_deslizamientos.geojson"
RIESGO_QUIMICO_GEOJSON = DATA_DIR / "riesgo_quimico.geojson"

# --- Cadastral land value (Tesorería Municipal de Saltillo) -----------------
# Published per colonia, which is the unit this project already works in, so
# the join needs no geometry at all — see DATOS.md §3.5. Informational layer:
# it does NOT enter the Investment Index. A low land value is genuinely
# ambiguous for a buyer (cheap entry or weak area), so giving it a sign in the
# score would bake in an undeclared thesis.
CATASTRO_PDF = RAW_DATA / "catastro" / "TABLAS_VALORES_SUELO_CONSTRUCCION_2026.pdf"
CATASTRO_JSON = DATA_DIR / "valor_catastral.json"
CATASTRO_FUENTE = (
    "Tesorería Municipal de Saltillo — Tablas de Valores de Suelo y "
    "Construcción (aprobadas por el Congreso de Coahuila)"
)
CATASTRO_EDICION = "2026"
# The cell separator inside the PDF content streams is the document's language
# tag, and it CHANGES between editions (es-ES in older ones, es-MX in 2026).
# Hardcoding either returns zero rows against the other, silently.
CATASTRO_SEPARADOR = re.compile(r"es-[A-Z]{2}")
# Terrain classes as printed, with the spelling drift the source actually
# contains: "RESIDENCIAL 1a." vs "RESIDENCIAL 1a", "RESIDENCIAL LUJO" vs
# "RESIDENCIAL DE LUJO", "MEDIO MEDIO" vs "MEDIA MEDIA". Left unnormalized,
# a handful of colonias fall through the value lookup with no error at all.
CATASTRO_CLASE = re.compile(
    r"^(POPULAR(\s*\(\d\))?|INTERES SOCIAL(\s*\(\d\))?|MEDI[OA] (BAJ[OA]|MEDI[OA]|ALT[OA])"
    r"|RESIDENCIAL(\s+(DE\s+)?LUJO|\s+1a\.?)?|ZONA TIPICA|INDUSTRIAL(\s*\(\d\))?"
    r"|CAMPESTRE|MARGINADO|LOCALIDAD\s*\(SOLAR\))\s*$", re.I)
CATASTRO_RUIDO = re.compile(
    r"CONGRESO|SOBERANO|ZARAGOZA|PODER LEGISLATIVO|TABLA|COLONIA O FRACC"
    r"|TIPO DE TERRENO|FRACCIONAMIENTOS \d{4}|^NO\.?$|^\d{1,3}$", re.I)
# Alphabet allowed in anything published from the cadastral PDF, mirroring
# CARACTERES_PERMITIDOS for the street index. Today the values cannot escape
# this anyway — the classes come from an anchored whitelist and the colonia
# names from a normalizer that strips every HTML metacharacter — but that
# invariant is spread across three functions, and loosening any one of them
# (a 2027 edition adding a class, or "stop destroying apostrophes in names")
# would dissolve it silently. This is the second layer the project says it wants.
CATASTRO_PERMITIDOS = re.compile(r"^[0-9A-ZÁÉÍÓÚÜÑ ().]+$")
# Ceiling per inflated PDF stream. The file is downloaded by hand rather than
# fetched by the pipeline, so this is not an exposed attack surface — but it is
# the one hand-rolled parser here pointed at a third-party binary, and 200 MB of
# zeros compresses to ~204 KB, so one crafted stream could take the machine out
# mid-run, after some layers are written and before others.
CATASTRO_MAX_FLUJO = 64 * 1024 * 1024

# 2020 Census variables used for the basic-services coverage index. The
# "positive" variants are used (dwellings that DO have the service):
# VPH_AGUADV instead of VPH_AGUAFV (the negative one).
COLUMNAS_SERVICIOS = ["VPH_C_ELEC", "VPH_AGUADV", "VPH_DRENAJ", "VPH_INTER"]

# Each entry maps a municipality to the locality folders (INEGI) that contain
# its AGEB layer. A locality with no "a" (AGEB) layer —common in small rural
# localities— is simply not included here.
MUNICIPIOS_AGEB: dict[str, list[Path]] = {
    "Saltillo": [
        RAW_DATA / "marco_geoestadistico" / "saltillo_map_ageb" / "050300001",
    ],
    # Pre-wired paths: the pipeline skips them gracefully while the folder does
    # not exist (prints "skipped" and continues), and picks them up as soon as
    # they are downloaded from INEGI (same product as Saltillo, see DATOS.md
    # §2.1). The locality keys were verified against Coahuila's 2020 Census:
    # Ramos Arizpe is municipality 027 (not 025), Arteaga 004.
    "Ramos Arizpe": [
        RAW_DATA / "marco_geoestadistico" / "ramos_arizpe_map_ageb" / "050270001",  # Ramos Arizpe (city)
    ],
    "Arteaga": [
        RAW_DATA / "marco_geoestadistico" / "arteaga_map_ageb" / "050040001",  # Arteaga (municipal seat)
        RAW_DATA / "marco_geoestadistico" / "arteaga_map_ageb" / "050040107",  # San Antonio de las Alazanas (sierra)
    ],
}


def cargar_ageb_municipio(nombre_municipio: str, carpetas_localidad: list[Path]) -> gpd.GeoDataFrame | None:
    """Load and combine the AGEB layers of all available localities of a municipality."""
    if not carpetas_localidad:
        print(f"  [{nombre_municipio}] No AGEB data downloaded yet, skipping.")
        return None

    capas = []
    for carpeta in carpetas_localidad:
        clave_localidad = carpeta.name
        shp_path = carpeta / "conjunto_de_datos" / f"{clave_localidad}a.shp"
        if not shp_path.exists():
            print(f"  [{nombre_municipio}] {shp_path} not found, skipping locality {clave_localidad}.")
            continue
        gdf = gpd.read_file(shp_path)
        capas.append(gdf)

    if not capas:
        return None

    gdf_municipio = pd.concat(capas, ignore_index=True)
    gdf_municipio = gpd.GeoDataFrame(gdf_municipio, geometry="geometry", crs=capas[0].crs)
    gdf_municipio["NOM_MUN"] = nombre_municipio
    return gdf_municipio


def filtrar_agebs_por_municipio() -> gpd.GeoDataFrame:
    """
    Combine the AGEBs of all municipalities configured in MUNICIPIOS_AGEB into
    a single GeoDataFrame, reprojected to EPSG:4326 (WGS84) for direct use in
    Leaflet.
    """
    print("Filtering AGEBs by municipality...")

    capas_municipio = []
    for nombre_municipio, carpetas in MUNICIPIOS_AGEB.items():
        gdf = cargar_ageb_municipio(nombre_municipio, carpetas)
        if gdf is not None:
            print(f"  [{nombre_municipio}] {len(gdf)} AGEBs loaded.")
            capas_municipio.append(gdf)

    if not capas_municipio:
        raise RuntimeError("No AGEB was loaded. Check the paths in MUNICIPIOS_AGEB.")

    gdf_final = pd.concat(capas_municipio, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs=capas_municipio[0].crs)
    gdf_final = gdf_final.to_crs(epsg=4326)

    print(f"\nCombined total: {len(gdf_final)} AGEBs in {gdf_final['NOM_MUN'].nunique()} municipality(ies).")
    return gdf_final


def cargar_frentes_de_manzana(columnas: list[str]) -> pd.DataFrame:
    """
    Load the "Frente de manzana" (fm) layer of every locality configured in
    MUNICIPIOS_AGEB, without geometry.

    Each record is one side of a block: it names the street it faces (NOMVIAL,
    TIPOVIAL), the settlement it belongs to (NOMASEN) and its postal code (CP),
    which is why the same layer feeds both the colonia name per AGEB and the
    street index.

    Args:
        columnas: attribute columns to read. CVEGEO is always added, since it is
            what ties a front to its AGEB.

    Returns:
        A DataFrame with the requested columns plus CVEGEO (truncated to the
        13-character AGEB key) and NOM_MUN. Empty if no locality is downloaded.
    """
    pedidas = ["CVEGEO"] + [c for c in columnas if c != "CVEGEO"]
    registros = []
    for nombre_municipio, carpetas in MUNICIPIOS_AGEB.items():
        for carpeta in carpetas:
            clave_localidad = carpeta.name
            shp_path = carpeta / "conjunto_de_datos" / f"{clave_localidad}fm.shp"
            if not shp_path.exists():
                continue
            df_fm = gpd.read_file(shp_path, columns=pedidas, ignore_geometry=True)
            df_fm["CVEGEO"] = df_fm["CVEGEO"].str[:13]
            df_fm["NOM_MUN"] = nombre_municipio
            registros.append(df_fm)

    if not registros:
        return pd.DataFrame(columns=pedidas + ["NOM_MUN"])
    return pd.concat(registros, ignore_index=True)


def cargar_nombres_colonias() -> pd.DataFrame:
    """
    Derive each AGEB's dominant colonia/settlement name from the "Frente de
    manzana" (fm) layer: group its records by AGEB (the first 13 characters of
    the front's CVEGEO match the AGEB's CVEGEO) and take the most frequent
    NOMASEN, ignoring INEGI's filler values (VALORES_SIN_ASENTAMIENTO). If an
    AGEB has no real name, it is labeled SIN_COLONIA instead of propagating the
    filler to the map.
    """
    df_fm = cargar_frentes_de_manzana(["NOMASEN"])
    if df_fm.empty:
        return pd.DataFrame(columns=["CVEGEO", "COLONIA"])

    def _colonia_dominante(grupo: pd.DataFrame) -> str:
        nombres = grupo["NOMASEN"].astype(str).str.strip()
        con_dato = nombres[~nombres.str.upper().isin(VALORES_SIN_ASENTAMIENTO)]
        if con_dato.empty:
            return SIN_COLONIA
        return con_dato.value_counts().idxmax()

    colonias = df_fm.groupby("CVEGEO").apply(_colonia_dominante, include_groups=False)
    return colonias.rename("COLONIA").reset_index()


def construir_indice_calles() -> dict:
    """
    Build the street -> settlement index the frontend search consumes, from the
    same "Frente de manzana" layer that gives each AGEB its colonia name.

    INEGI already pairs street and settlement in a single record, so no spatial
    work is needed: grouping the fronts by (street, type, settlement,
    municipality) yields, for each street, every settlement it runs through.

    Two decisions worth stating, because both were measured:

    - **No geometry is stored.** Each zone carries the AGEBs it touches instead,
      and the browser resolves position from the AGEB polygons it has already
      loaded. Storing per-street bounding boxes would roughly triple the file to
      buy precision finer than the AGEB, which is the unit every figure in this
      app is published at.
    - **Zones are grouped by the front's own NOMASEN, not by the colonia the map
      assigns to its AGEB.** Those disagree for 42.1% of street fronts, because
      an AGEB routinely spans several settlements and the map keeps the dominant
      one. Grouping by the map's name would be self-consistent but would answer
      "which colonia is this street in?" with a name the street may have nothing
      to do with. The frontend shows the settlement found here and, when the
      sector is published under a different colonia, says so on the card rather
      than hiding the discrepancy.

    Returns:
        A JSON-ready dict. The bulky part is `calles`, one entry per street name
        holding its zones as index tuples into the small lookup lists, which is
        what keeps repeated settlement and municipality names from being spelled
        out ~13,000 times.
    """
    df = cargar_frentes_de_manzana(["TIPOVIAL", "NOMVIAL", "NOMASEN", "CP"])
    if df.empty:
        return {}

    for columna in ["TIPOVIAL", "NOMVIAL", "NOMASEN", "CP"]:
        df[columna] = df[columna].astype(str).str.strip()

    total_frentes = len(df)
    df = df[~df["TIPOVIAL"].str.upper().isin(TIPOS_NO_VIALIDAD)]
    df = df[~df["NOMVIAL"].str.upper().isin(VALORES_SIN_VIALIDAD)]
    df = df[~df["NOMASEN"].str.upper().isin(VALORES_SIN_ASENTAMIENTO)]
    print(f"  {total_frentes} block fronts, {len(df)} with a real street and settlement.")

    zonas = (
        df.groupby(["NOMVIAL", "TIPOVIAL", "NOMASEN", "NOM_MUN"])
        .agg(
            agebs=("CVEGEO", lambda s: sorted(set(s))),
            # A settlement can straddle two postal codes; the dominant one is
            # the useful hint, and it is only ever shown as a hint.
            cp=("CP", lambda s: s.value_counts().idxmax()),
        )
        .reset_index()
    )

    # Merge the zones that resolve to the SAME sectors under the same road type.
    # Two such zones are one answer, not two: the card they open is built
    # entirely from the AGEB, so offering them separately asks the user to
    # choose between identical outcomes — a choice the data cannot back. It
    # happens to 1,553 groups (14.5% of zones), because an AGEB routinely spans
    # several settlements and INEGI records different NOMASEN on different
    # fronts of the same street inside it. Every settlement name is kept, joined
    # onto the one zone; none is dropped.
    #
    # The road type stays in the key on purpose: a CALLE and a PRIVADA of the
    # same name in the same sector are two different roads, and merging them
    # would erase a real distinction (519 groups). Municipality is not in the
    # key because it cannot differ — the sectors determine it, verified: 0
    # groups with more than one.
    fusionadas: dict[tuple, dict] = {}
    for zona in zonas.itertuples(index=False):
        clave = (zona.NOMVIAL, zona.TIPOVIAL, tuple(zona.agebs))
        grupo = fusionadas.setdefault(clave, {
            "municipio": zona.NOM_MUN, "asentamientos": set(), "cps": set(),
        })
        grupo["asentamientos"].add(zona.NOMASEN)
        grupo["cps"].add(zona.cp)

    tipos = sorted({clave[1] for clave in fusionadas})
    asentamientos = sorted({a for g in fusionadas.values() for a in g["asentamientos"]})
    municipios = sorted({g["municipio"] for g in fusionadas.values()})
    cps = sorted({c for g in fusionadas.values() for c in g["cps"]})
    agebs = sorted({a for clave in fusionadas for a in clave[2]})

    tipos = sorted(zonas["TIPOVIAL"].unique())
    asentamientos = sorted(zonas["NOMASEN"].unique())
    municipios = sorted(zonas["NOM_MUN"].unique())
    cps = sorted(zonas["cp"].unique())
    agebs = sorted({a for lista in zonas["agebs"] for a in lista})

    idx_tipo = {v: i for i, v in enumerate(tipos)}
    idx_asen = {v: i for i, v in enumerate(asentamientos)}
    idx_muni = {v: i for i, v in enumerate(municipios)}
    idx_cp = {v: i for i, v in enumerate(cps)}
    idx_ageb = {v: i for i, v in enumerate(agebs)}

    calles: dict[str, list] = {}
    for (nombre, tipo, claves_ageb), grupo in sorted(fusionadas.items()):
        calles.setdefault(nombre, []).append([
            idx_tipo[tipo],
            [idx_asen[a] for a in sorted(grupo["asentamientos"])],
            idx_muni[grupo["municipio"]],
            [idx_cp[c] for c in sorted(grupo["cps"])],
            [idx_ageb[a] for a in claves_ageb],
        ])

    print(
        f"  {len(calles)} street names, {len(fusionadas)} zones "
        f"(merged down from {len(zonas)}), {len(agebs)} AGEBs referenced."
    )
    return {
        # Shape version. The page fetches this file with `no-cache`, so a fresh
        # index reliably reaches a page that may itself be a cached older
        # version — and an older parser reading a newer shape does not fail, it
        # renders "undefined" into the interface, which is worse than failing.
        # Bump this whenever the zone tuple changes; the frontend refuses a
        # version it does not know and says so instead of showing garbage.
        "formato": FORMATO_INDICE_CALLES,
        "fuente": INEGI_VECTORIAL_FUENTE,
        "fecha_corte": INEGI_VECTORIAL_FECHA_CORTE,
        "tipos": tipos,
        "asentamientos": asentamientos,
        "municipios": municipios,
        "cps": cps,
        "agebs": agebs,
        "calles": [[nombre, zs] for nombre, zs in sorted(calles.items())],
    }


# Characters the published names are allowed to contain: capitals (accented
# included), digits, spaces and the punctuation INEGI actually uses. This is a
# guard on what reaches a public page, not a data-cleaning step — the index is
# generated from shapefiles that live outside the repo (`raw_data/` is
# gitignored), so a reviewer looking at a diff of the generated file cannot
# check the input that produced it. Anything outside this set means the source
# changed in a way nobody has looked at, and the pipeline should stop rather
# than publish it.
CARACTERES_PERMITIDOS = re.compile(r"^[0-9A-ZÁÉÍÓÚÜÑ '(),./-]+$")


def validar_nombres_publicados(indice: dict) -> None:
    """
    Fail loudly if any name headed for the public page contains an unexpected
    character.

    Raises:
        ValueError: listing the offending values, at most a handful.
    """
    sospechosos = []
    for campo in ["tipos", "asentamientos", "municipios", "cps"]:
        sospechosos += [(campo, v) for v in indice[campo]
                        if not CARACTERES_PERMITIDOS.match(v.upper())]
    sospechosos += [("calles", nombre) for nombre, _ in indice["calles"]
                    if not CARACTERES_PERMITIDOS.match(nombre.upper())]
    if sospechosos:
        muestra = ", ".join(f"{campo}: {valor!r}" for campo, valor in sospechosos[:5])
        raise ValueError(
            f"{len(sospechosos)} name(s) with unexpected characters, refusing to "
            f"publish the street index. First few — {muestra}"
        )


def exportar_indice_calles(indice: dict) -> None:
    """
    Write the street index to data/: compact JSON, but **one line per street**.

    The line breaks are the point. As a single line the file was 429 KB with no
    newline in it, so every future change rendered in `git diff` as one deleted
    line and one added line — unreviewable. One street per line costs ~0.1% in
    size and makes the diff say which streets actually moved.
    """
    if not indice:
        print("  No street index generated (no Frente de manzana layer found).")
        return

    validar_nombres_publicados(indice)

    compacto = {"ensure_ascii": False, "separators": (",", ":")}
    cabecera = {clave: valor for clave, valor in indice.items() if clave != "calles"}
    # Splice the streets in by hand so each gets its own line; json.dumps has no
    # option for "compact except at this one nesting level".
    texto = (
        json.dumps(cabecera, **compacto)[:-1]
        + ',"calles":[\n'
        + ",\n".join(json.dumps(calle, **compacto) for calle in indice["calles"])
        + "\n]}"
    )
    # Hand-spliced JSON gets parsed back and compared before it is written: a
    # malformed or reordered file would break the search at runtime, far from
    # here.
    if json.loads(texto) != indice:
        raise ValueError("The serialized street index does not match the source data.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CALLES_JSON.write_text(texto, encoding="utf-8")
    tamano_kb = CALLES_JSON.stat().st_size / 1024
    print(f"  Street index exported: {CALLES_JSON} ({tamano_kb:.1f} KB, "
          f"{len(indice['calles'])} lines)")


def _normalizar_catastro(texto: str) -> str:
    """Fold a colonia name for matching: accents, case, punctuation, and the
    zero padding the cadastre uses on dates ("05 DE MAYO" vs "5 DE MAYO")."""
    plano = unicodedata.normalize("NFD", texto)
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    plano = re.sub(r"[^\w\s]", " ", plano.upper())
    plano = re.sub(r"\s+", " ", plano).strip()
    return re.sub(r"\b0(\d)\b", r"\1", plano)


def _normalizar_clase(clase: str) -> str:
    """Collapse the source's own spelling drift onto one label per class."""
    c = re.sub(r"\s+", " ", clase.upper().replace(".", "")).strip()
    c = c.replace("MEDIA MEDIA", "MEDIO MEDIO").replace("MEDIA ", "MEDIO ")
    c = c.replace("RESIDENCIAL LUJO", "RESIDENCIAL DE LUJO")
    return c


def extraer_tablas_catastrales() -> tuple[dict[str, float], dict[str, str]]:
    """
    Read the cadastral PDF: the value per terrain class, and the class of each
    colonia.

    The PDF carries real embedded text, so no OCR and no PDF dependency is
    needed — inflating its FlateDecode streams with the standard library and
    reading the text-showing operators is enough. Note that a fetch tool
    reporting the file as "unreadable" means only that it did not inflate the
    streams; it is not evidence of a scan.

    Returns:
        (value per normalized class in pesos/m², class per normalized colonia).
        Both empty if the PDF is not present, so the pipeline can continue.
    """
    if not CATASTRO_PDF.exists():
        print(f"  Notice: {CATASTRO_PDF} not found; skipping cadastral values.")
        return {}, {}

    crudo = CATASTRO_PDF.read_bytes()
    literal = re.compile(rb"\((?:\\.|[^()\\])*\)", re.S)
    escape = re.compile(rb"\\([()\\])")
    paginas: list[str] = []
    for m in re.finditer(rb"stream\r?\n", crudo):
        ini = m.end()
        fin = crudo.find(b"endstream", ini)
        if fin == -1:
            continue
        try:
            descompresor = zlib.decompressobj()
            flujo = descompresor.decompress(crudo[ini:fin], CATASTRO_MAX_FLUJO)
            if descompresor.unconsumed_tail:
                print(f"  Warning: stream at byte {ini} inflates past "
                      f"{CATASTRO_MAX_FLUJO // 1048576} MB; skipped.")
                continue
        except zlib.error:
            continue  # image or already-uncompressed stream
        if b"Tj" in flujo or b"TJ" in flujo:
            paginas.append("".join(
                escape.sub(rb"\1", s.group(0)[1:-1]).decode("latin-1")
                for s in literal.finditer(flujo)
            ))

    # Table 1: class -> $/m2. Printed as "0POPULAR (1)$263.18 1POPULAR (2)..."
    valores: dict[str, float] = {}
    for pagina in paginas:
        if "VALOR APLICABLE POR M" not in pagina:
            continue
        # The label must START with a letter, which is what keeps the row index
        # ("11INDUSTRIAL (2)") out of it, but digits have to be allowed INSIDE
        # or every class written with a numeral — POPULAR (2), INTERES SOCIAL
        # (2), INDUSTRIAL (2) — silently fails to match. Those three are among
        # the most common classes in the tables.
        for m in re.finditer(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s()\.\da]{3,40}?)\$([\d,]+\.\d{2})",
                             pagina):
            etiqueta = _normalizar_clase(re.sub(r"^\d+", "", m.group(1)).strip())
            if CATASTRO_CLASE.match(etiqueta):
                valores[etiqueta] = float(m.group(2).replace(",", ""))
        break

    # Table 2: colonia -> class. A class label always follows the colonia it
    # classifies, so the nearest preceding non-class cell is the name.
    colonias: dict[str, str] = {}
    for pagina in paginas:
        if not CATASTRO_SEPARADOR.search(pagina):
            continue
        pendiente = None
        for celda in (c.strip() for c in CATASTRO_SEPARADOR.split(pagina)):
            if not celda or CATASTRO_RUIDO.search(celda):
                continue
            if CATASTRO_CLASE.match(celda):
                if pendiente:
                    colonias.setdefault(_normalizar_catastro(pendiente),
                                        _normalizar_clase(celda))
                    pendiente = None
            else:
                pendiente = celda

    print(f"  Cadastral tables read: {len(valores)} terrain classes, "
          f"{len(colonias)} colonias (edition {CATASTRO_EDICION}).")
    # A present-but-unparsable PDF is the dangerous case, not a missing one:
    # the export would return early, leave the PREVIOUS valor_catastral.json in
    # place, and the run would still report success — shipping last year's
    # figures under this year's edition label. The tables are reissued yearly
    # and their internals already drift, so this is a "when", not an "if".
    if not colonias or not valores:
        raise ValueError(
            f"{CATASTRO_PDF} was read but yielded {len(valores)} classes and "
            f"{len(colonias)} colonias. The layout probably changed (the cell "
            f"separator is a language tag and varies by edition). Refusing to "
            f"continue rather than silently republish the previous file."
        )
    faltantes = {c for c in colonias.values() if c not in valores}
    if faltantes:
        # Loud rather than silent: a class with no value would publish a
        # colonia with no figure and no explanation.
        print(f"  Warning: {len(faltantes)} class(es) with no value in the "
              f"table: {sorted(faltantes)}")
    return valores, colonias


def asignar_valor_catastral(
    gdf_ageb_servicios: gpd.GeoDataFrame,
    valores: dict[str, float],
    colonias: dict[str, str],
) -> dict:
    """
    Attach a cadastral class and value to each AGEB through its colonia name.

    Matching is deliberately conservative: an exact fold first, then equality
    of the *set* of words, which catches the real reordering in the data
    ("AMPLIACIÓN 26 DE MARZO" vs "26 DE MARZO AMPLIACION"). Word-*subset*
    matching was measured and rejected: it would pair the app's "AMISTAD" with
    the cadastre's "AMISTAD III", and a land value bound to the wrong colonia
    is worse than no value at all. Anything unmatched is published as having no
    figure, the same way MOTIVO_SIN_DATO handles missing Census cells.
    """
    por_palabras: dict[frozenset, tuple[str, str]] = {}
    # Spacing alone differs often enough to matter ("VISTA HERMOSA" on the map,
    # "VISTAHERMOSA" in the tables). Collapsing it is a strict normalization,
    # not a fuzzy guess: two distinct colonias separated only by a space are
    # not a real case, whereas the miss is.
    sin_espacios: dict[str, tuple[str, str]] = {}
    for nombre, clase in colonias.items():
        por_palabras.setdefault(frozenset(nombre.split()), (nombre, clase))
        sin_espacios.setdefault(nombre.replace(" ", ""), (nombre, clase))

    sectores: dict[str, dict] = {}
    conteo = {"exacto": 0, "palabras": 0, "espacios": 0, "sin_dato": 0}
    for _, fila in gdf_ageb_servicios.iterrows():
        if str(fila.get("NOM_MUN", "")).upper() != "SALTILLO":
            continue  # the tables cover the municipality of Saltillo only
        colonia = fila.get("COLONIA")
        if not colonia or colonia == "SIN_COLONIA":
            continue
        plano = _normalizar_catastro(colonia)
        if plano in colonias:
            nombre_catastro, clase, via = colonia, colonias[plano], "exacto"
        elif frozenset(plano.split()) in por_palabras:
            nombre_catastro, clase = por_palabras[frozenset(plano.split())]
            via = "palabras"
        elif plano.replace(" ", "") in sin_espacios:
            nombre_catastro, clase = sin_espacios[plano.replace(" ", "")]
            via = "espacios"
        else:
            conteo["sin_dato"] += 1
            continue
        conteo[via] += 1
        sectores[fila["CVEGEO"]] = {
            "clase": clase,
            "valor": valores.get(clase),
            # Recorded so the card can say how the figure was reached: on a
            # word-set match the cadastre files the colonia under a differently
            # ordered name, and hiding that would contradict the map's label.
            "via": via,
            **({"nombre_catastro": nombre_catastro} if via != "exacto" else {}),
        }

    total = sum(conteo.values())
    if total:
        print(f"  Cadastral value matched to {len(sectores)} of {total} Saltillo "
              f"AGEBs ({len(sectores) / total:.1%}): {conteo['exacto']} exact, "
              f"{conteo['palabras']} by word set, {conteo['espacios']} by spacing, "
              f"{conteo['sin_dato']} with no published row.")
    return sectores


def validar_registros_catastrales(sectores: dict) -> None:
    """
    Refuse to publish a cadastral record whose contents are not what the
    frontend is built to receive.

    Mirrors `validar_nombres_publicados` for the street index, and raises for
    the same reason: the alternative is a browser discovering the problem in
    front of a user, far from here. The value check is not cosmetic — a class
    listed for a colonia but absent from the value table exports as `null`, the
    map still paints it, and only the click reveals it.

    Raises:
        ValueError: listing the offending records, at most a handful.
    """
    malos = []
    for clave, registro in sectores.items():
        if not CATASTRO_PERMITIDOS.match(registro["clase"]):
            malos.append((clave, "clase", registro["clase"]))
        alias = registro.get("nombre_catastro")
        if alias is not None and not CATASTRO_PERMITIDOS.match(alias):
            malos.append((clave, "nombre_catastro", alias))
        if not isinstance(registro["valor"], (int, float)):
            malos.append((clave, "valor", registro["valor"]))

    if malos:
        muestra = ", ".join(f"{c} {campo}={v!r}" for c, campo, v in malos[:5])
        raise ValueError(
            f"{len(malos)} cadastral record(s) with unexpected content, refusing "
            f"to publish the layer. First few — {muestra}"
        )


def exportar_valor_catastral(sectores: dict) -> None:
    """
    Write the cadastral lookup to data/: keyed by AGEB, one sector per line.

    No geometry on purpose. The browser already holds the AGEB polygons from
    the services layer, and a third copy of them would cost ~640 KB against
    the 5 MB budget of SPEC §2 — which data/ is already close to. One line per
    sector for the same reason as the street index: a single-line file renders
    every future change as one deleted and one added line, unreviewable.
    """
    if not sectores:
        print("  No cadastral values to export.")
        return

    validar_registros_catastrales(sectores)

    compacto = {"ensure_ascii": False, "separators": (",", ":")}
    cabecera = {
        "fuente": CATASTRO_FUENTE,
        "edicion": CATASTRO_EDICION,
        # Carried in the file rather than the frontend so the warning travels
        # with the data: this is a tax base, not a market price.
        "nota": ("Valor catastral de referencia (base fiscal), no precio de "
                 "mercado. Es una clase asignada a toda la colonia, no un "
                 "avalúo del predio."),
    }
    texto = (
        json.dumps(cabecera, **compacto)[:-1]
        + ',"sectores":{\n'
        + ",\n".join(f"{json.dumps(clave, **compacto)}:{json.dumps(valor, **compacto)}"
                     for clave, valor in sorted(sectores.items()))
        + "\n}}"
    )
    if json.loads(texto)["sectores"] != sectores:
        raise ValueError("The serialized cadastral index does not match the source data.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CATASTRO_JSON.write_text(texto, encoding="utf-8")
    print(f"  Cadastral values exported: {CATASTRO_JSON} "
          f"({CATASTRO_JSON.stat().st_size / 1024:.1f} KB, {len(sectores)} sectors)")


def cargar_censo_servicios() -> pd.DataFrame:
    """
    Load the 2020 Census CSV by urban AGEB (all of Coahuila) and keep only the
    AGEB-level rows (excluding state/municipality/locality totals and the
    per-block detail) of the municipalities in MUNICIPIOS_AGEB.
    """
    df = pd.read_csv(CENSO_CSV, dtype=str, low_memory=False)

    filas_ageb = (df["MZA"] == "000") & (df["AGEB"] != "0000")
    df = df[filas_ageb].copy()
    df = df[df["NOM_MUN"].isin(MUNICIPIOS_AGEB.keys())]

    df["CVEGEO"] = df["ENTIDAD"] + df["MUN"] + df["LOC"] + df["AGEB"]

    # POBTOT and TVIVHAB are not masked in these municipalities (verified: 0
    # asterisks), so a non-numeric value here really is a genuine 0.
    for col in ["POBTOT", "TVIVHAB"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # INEGI masks small counts (1-2 dwellings) with "*" for confidentiality.
    # They are NOT filled with 0 here: "masked" and "zero" are different things
    # and confusing them made an AGEB with no published data render as if it had
    # 0% coverage. The distinction is resolved in calcular_cobertura_servicios(),
    # which can see how many of the four columns are missing.
    for col in COLUMNAS_SERVICIOS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["SERVICIOS_ENMASCARADOS"] = df[COLUMNAS_SERVICIOS].isna().sum(axis=1)

    return df[
        [
            "CVEGEO",
            "NOM_MUN",
            "POBTOT",
            "TVIVHAB",
            "SERVICIOS_ENMASCARADOS",
            *COLUMNAS_SERVICIOS,
        ]
    ]


def calcular_cobertura_servicios(df_censo: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the % of dwellings with each basic service and a composite index
    (SERVICIOS_INDEX) as the average of the four. The Census aggregated at AGEB
    level only gives totals per service, not the real joint combination per
    dwelling, so this average is the best available approximation to "% of
    dwellings with all services" without using microdata.
    """
    df = df_censo.copy()
    tviv_seguro = df["TVIVHAB"].astype(float).replace(0, np.nan)

    # An AGEB has no coverage data when (a) there are no dwellings to serve or
    # (b) INEGI masked ALL FOUR service columns. In both cases the index stays
    # NaN and the frontend paints it as "no data" in gray, instead of lying with
    # a 0% that would read as the worst coverage in the city.
    sin_viviendas = df["TVIVHAB"] == 0
    todo_enmascarado = df["SERVICIOS_ENMASCARADOS"] == len(COLUMNAS_SERVICIOS)

    df["MOTIVO_SIN_DATO"] = np.where(
        sin_viviendas,
        "Sin viviendas habitadas registradas en el Censo 2020",
        np.where(
            todo_enmascarado,
            "Cifras enmascaradas por INEGI (confidencialidad: 1-2 viviendas)",
            None,
        ),
    )

    # Partial masking (1-3 of 4 columns): it is computable. The asterisk means
    # 1-2 dwellings out of a much larger total, so treating that column as 0%
    # approximates reality instead of dropping the whole AGEB.
    servicios = df[COLUMNAS_SERVICIOS]
    servicios = servicios.mask(~todo_enmascarado & servicios.isna(), 0)

    df["PCT_ELECTRICIDAD"] = servicios["VPH_C_ELEC"] / tviv_seguro * 100
    df["PCT_AGUA"] = servicios["VPH_AGUADV"] / tviv_seguro * 100
    df["PCT_DRENAJE"] = servicios["VPH_DRENAJ"] / tviv_seguro * 100
    df["PCT_INTERNET"] = servicios["VPH_INTER"] / tviv_seguro * 100

    df["SERVICIOS_INDEX"] = df[
        ["PCT_ELECTRICIDAD", "PCT_AGUA", "PCT_DRENAJE", "PCT_INTERNET"]
    ].mean(axis=1)

    return df


def integrar_censo_a_ageb(
    gdf_agebs: gpd.GeoDataFrame, df_servicios: pd.DataFrame, df_colonias: pd.DataFrame
) -> gpd.GeoDataFrame:
    """Join the AGEB polygons with the Census service variables and the colonia name, by CVEGEO."""
    columnas_censo = [
        "CVEGEO",
        "POBTOT",
        "TVIVHAB",
        "PCT_ELECTRICIDAD",
        "PCT_AGUA",
        "PCT_DRENAJE",
        "PCT_INTERNET",
        "SERVICIOS_INDEX",
        "MOTIVO_SIN_DATO",
    ]
    gdf_unido = gdf_agebs.merge(df_servicios[columnas_censo], on="CVEGEO", how="left")
    gdf_unido = gdf_unido.merge(df_colonias, on="CVEGEO", how="left")
    gdf_unido["COLONIA"] = gdf_unido["COLONIA"].fillna("Sin nombre de colonia")

    # An AGEB that doesn't even appear in the Census is a third "no data" case
    # and deserves its own explanation in the card.
    sin_registro = gdf_unido["SERVICIOS_INDEX"].isna() & gdf_unido["MOTIVO_SIN_DATO"].isna()
    gdf_unido.loc[sin_registro, "MOTIVO_SIN_DATO"] = "Sin registro en el Censo 2020"

    sin_dato = gdf_unido["SERVICIOS_INDEX"].isna().sum()
    if sin_dato:
        print(f"  Notice: {sin_dato} AGEB(s) with no service data. Breakdown:")
        for motivo, n in gdf_unido["MOTIVO_SIN_DATO"].value_counts().items():
            print(f"    - {motivo}: {n}")

    return gdf_unido


def cargar_denue() -> gpd.GeoDataFrame:
    """
    Load DENUE (all of Coahuila), filter it to the configured municipalities
    and classify each establishment into an urban amenity category (escuela,
    salud, supermercado) according to CATEGORIAS_DENUE.
    """
    df = pd.read_csv(DENUE_CSV, dtype=str, low_memory=False, encoding="latin-1")
    df = df[df["municipio"].isin(MUNICIPIOS_AGEB.keys())].copy()

    categorias = pd.Series(pd.NA, index=df.index, dtype="object")
    for nombre_categoria, condicion in CATEGORIAS_DENUE.items():
        categorias = categorias.where(~condicion(df), nombre_categoria)
    df["CATEGORIA"] = categorias
    df = df.dropna(subset=["CATEGORIA", "latitud", "longitud"])

    gdf = gpd.GeoDataFrame(
        df[["CATEGORIA"]],
        geometry=gpd.points_from_xy(df["longitud"].astype(float), df["latitud"].astype(float)),
        crs="EPSG:4326",
    )
    print(f"  DENUE: {len(gdf)} relevant establishments ({gdf['CATEGORIA'].value_counts().to_dict()}).")
    return gdf


def calcular_indice_comercios(gdf_agebs: gpd.GeoDataFrame, gdf_denue: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each AGEB, compute a 0-100 proximity score to each urban amenity
    category (distance from the AGEB centroid to the nearest establishment,
    with linear decay up to RADIO_MAX_KM) and average them into COMERCIOS_INDEX.
    """
    centroides = gdf_agebs[["CVEGEO", "geometry"]].to_crs(CRS_METRICO).copy()
    centroides["geometry"] = centroides.geometry.centroid

    gdf_denue_m = gdf_denue.to_crs(CRS_METRICO)

    resultado = centroides[["CVEGEO"]].copy()
    columnas_score = []
    for categoria in CATEGORIAS_DENUE:
        columna_score = f"SCORE_{categoria.upper()}"
        columnas_score.append(columna_score)

        puntos_categoria = gdf_denue_m[gdf_denue_m["CATEGORIA"] == categoria]
        if puntos_categoria.empty:
            resultado[columna_score] = 0.0
            continue

        cercano = gpd.sjoin_nearest(
            centroides, puntos_categoria[["geometry"]], distance_col="DIST_M"
        )
        # sjoin_nearest can produce more than one match on a distance tie;
        # we keep the minimum distance per AGEB.
        distancia_km = cercano.groupby("CVEGEO")["DIST_M"].min() / 1000
        score = (100 * (1 - distancia_km / RADIO_MAX_KM)).clip(lower=0)
        resultado[columna_score] = resultado["CVEGEO"].map(score).fillna(0)

    resultado["COMERCIOS_INDEX"] = resultado[columnas_score].mean(axis=1)
    return resultado


def cargar_riesgo_implan(shp_path: Path, campo_intensidad: str) -> gpd.GeoDataFrame:
    """
    Load an IMPLAN risk shapefile (CARTO SALTILLO), normalize the intensity
    level to the standard scale (Muy bajo→Muy alto) and reproject to EPSG:4326
    for the frontend. Returns all polygons (unfiltered).
    """
    gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
    # The shapefiles use different capitalization ("Muy alto" vs "muy bajo");
    # normalize to the "Xxxx xxxx" form.
    gdf["INTENSIDAD"] = gdf[campo_intensidad].str.strip().str.capitalize()
    return gdf


def preparar_capa_riesgo(
    gdf_riesgo: gpd.GeoDataFrame, niveles: list[str] = NIVELES_ELEVADOS
) -> gpd.GeoDataFrame:
    """
    Filter to the relevant risk levels and dissolve by intensity level,
    producing a lightweight GeoDataFrame (one multipolygon per level), ordered
    from lowest to highest intensity, with each level's 0-100 score. This
    geometry feeds both the Investment Index penalty and the visible layer
    (which additionally splits it into zones on export, see
    `exportar_capa_riesgo`), guaranteeing consistency.

    `niveles` is the threshold of which levels are kept; by default
    `NIVELES_ELEVADOS` (discards only "Muy bajo", the background of ~90-98% of
    the area). A layer may pass a higher threshold: e.g. chemical-technological
    risk also discards "Bajo" because there that level covers 93% of the grid
    (the model's background, no discriminating value) and, without trimming it,
    the layer alone would exceed the project's 5 MB limit.
    """
    sub = gdf_riesgo[gdf_riesgo["INTENSIDAD"].isin(niveles)]
    disuelto = sub.dissolve(by="INTENSIDAD", as_index=False)[["INTENSIDAD", "geometry"]]
    disuelto["PUNTAJE"] = disuelto["INTENSIDAD"].map(PUNTAJE_INTENSIDAD)
    orden = {nivel: i for i, nivel in enumerate(NIVELES_INTENSIDAD)}
    disuelto = disuelto.sort_values(
        "INTENSIDAD", key=lambda s: s.map(orden)
    ).reset_index(drop=True)
    return disuelto


def exportar_capa_riesgo(
    gdf_disuelto: gpd.GeoDataFrame, salida: Path, titulo: str, fenomeno: str
) -> gpd.GeoDataFrame:
    """
    Simplify the geometry, split each level's multipolygon into its individual
    zones, attach traceability metadata (title, phenomenon,
    source and cutoff date) and export the risk layer to data/ ready for
    Leaflet.

    The `explode` is what lets a single zone highlight on the map when hovered,
    rather than every blotch of the same level across the city: with the
    dissolved multipolygon, Leaflet sees a single element per level. It does not
    alter the geometry (same shape, declared as several features); it only
    repeats the properties on each one, at a cost of about ~450 KB total across
    the two layers, well below the project's 5 MB limit.

    It is exploded here and not in `preparar_capa_riesgo` on purpose: the
    dissolved version still feeds the Investment Index penalty, where having a
    single geometry per level is the natural choice for the overlay.
    """
    gdf = gdf_disuelto.copy()
    gdf["geometry"] = gdf["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )
    niveles = len(gdf)
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    gdf["TITULO"] = titulo
    gdf["FENOMENO"] = fenomeno
    gdf["FUENTE"] = IMPLAN_FUENTE
    gdf["FECHA"] = IMPLAN_FECHA_CORTE

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(salida, driver="GeoJSON")
    tamano_kb = salida.stat().st_size / 1024
    print(
        f"  Risk layer exported: {salida} "
        f"({niveles} levels, {len(gdf)} zones, {tamano_kb:.1f} KB)"
    )
    return gdf


def agebs_evaluados_por_riesgo(
    gdf_agebs: gpd.GeoDataFrame, gdf_riesgo_completo: gpd.GeoDataFrame
) -> set[str]:
    """
    Which AGEBs the flood model actually looked at.

    This is the difference between "no exposure" and "not assessed", and it is
    not decorative: the IMPLAN Atlas covers the municipality of Saltillo only,
    so an AGEB in Ramos Arizpe or Arteaga has no flood figure for the same
    reason a masked Census cell has no coverage figure -- nobody measured it.
    Treating that as zero hands those sectors a guaranteed no-penalty in the
    Investment Index, which is a reward for OUR missing data.

    Coverage is derived from the model's own extent rather than from a
    municipality name, for the same reason the frontend derives layer
    availability from each GeoJSON's bounds: a hardcoded `== "Saltillo"` would
    be a magic value that silently goes stale the day another city's atlas
    arrives, which is precisely the expansion this pipeline is meant to allow.

    `gdf_riesgo_completo` must be the UNFILTERED mesh: a cell classed "Muy
    bajo" was still assessed, it just is not published as a risk zone.
    """
    malla = gdf_riesgo_completo[["geometry"]].to_crs(CRS_METRICO)
    agebs = gdf_agebs[["CVEGEO", "geometry"]].to_crs(CRS_METRICO)
    tocados = gpd.sjoin(agebs, malla, how="inner", predicate="intersects")
    return set(tocados["CVEGEO"].unique())


def calcular_riesgo_inundacion_por_ageb(
    gdf_agebs: gpd.GeoDataFrame,
    gdf_inundacion: gpd.GeoDataFrame,
    gdf_riesgo_completo: gpd.GeoDataFrame | None = None,
) -> pd.DataFrame:
    """
    Compute RIESGO_INDEX (0-100) per AGEB as area-weighted flood exposure:
    sum(level_intersection_area × level_score) over the AGEB's total area. An
    AGEB inside the model's coverage with no intersection with elevated risk →
    0; an AGEB the model never covered → NaN, which is a different statement.
    The computation is done in a metric CRS (EPSG:6372) for correct areas.
    """
    agebs_m = gdf_agebs[["CVEGEO", "geometry"]].to_crs(CRS_METRICO).copy()
    agebs_m["AREA_AGEB"] = agebs_m.geometry.area

    riesgo_m = gdf_inundacion[["INTENSIDAD", "PUNTAJE", "geometry"]].to_crs(CRS_METRICO)

    interseccion = gpd.overlay(
        agebs_m[["CVEGEO", "geometry"]], riesgo_m, how="intersection", keep_geom_type=True
    )
    interseccion["APORTE"] = interseccion.geometry.area * interseccion["PUNTAJE"]
    aporte_por_ageb = interseccion.groupby("CVEGEO")["APORTE"].sum()

    resultado = agebs_m[["CVEGEO", "AREA_AGEB"]].copy()
    resultado["APORTE"] = resultado["CVEGEO"].map(aporte_por_ageb).fillna(0)
    resultado["RIESGO_INDEX"] = (resultado["APORTE"] / resultado["AREA_AGEB"]).clip(0, 100)

    if gdf_riesgo_completo is not None:
        evaluados = agebs_evaluados_por_riesgo(gdf_agebs, gdf_riesgo_completo)
        fuera = ~resultado["CVEGEO"].isin(evaluados)
        resultado.loc[fuera, "RIESGO_INDEX"] = float("nan")
        print(
            f"  Flood model coverage: {len(evaluados)} AGEBs assessed, "
            f"{int(fuera.sum())} outside the Atlas (no figure, not a zero)."
        )

    return resultado[["CVEGEO", "RIESGO_INDEX"]]


def calcular_indice_inversion(
    gdf_ageb_servicios: gpd.GeoDataFrame,
    df_comercios: pd.DataFrame,
    df_riesgo: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """
    Compute the Real-Estate Investment Index. The base index combines
    Services (0.4) and Comercios (0.3) renormalized to 0-100; on top of it the
    flood-Risk penalty (0.3) is applied, subtracting up to 30 points based on
    the AGEB's exposure. The result is clipped to [0, 100].

    A sector the flood model never covered gets NO index at all, the same rule
    the services weight already follows: when a component of the weight is
    missing, there is no index to publish. It is not that the penalty happens
    to be zero -- it is that 30% of what the number means was never measured,
    and the missing term can only move a score UP, so publishing it would
    flatter those sectors for a gap in OUR data.

    That was measurable before this rule: with the old `fillna(0)`, Ramos
    Arizpe put 33% of its AGEBs in the index's top quintile against Saltillo's
    20%, where on a level field the two sit at 23% and 21%. Flagging it was not
    enough, because the colour ramp still ranked them; only leaving them out of
    the scale does. Same error the Census fix (MOTIVO_SIN_DATO) corrected once:
    absence of a figure is not a zero.
    """
    gdf = gdf_ageb_servicios.merge(df_comercios, on="CVEGEO", how="left")
    gdf = gdf.merge(df_riesgo, on="CVEGEO", how="left")
    gdf["RIESGO_EVALUADO"] = gdf["RIESGO_INDEX"].notna()

    peso_base = PESO_SERVICIOS + PESO_COMERCIOS
    base = (
        gdf["SERVICIOS_INDEX"] * PESO_SERVICIOS + gdf["COMERCIOS_INDEX"] * PESO_COMERCIOS
    ) / peso_base
    gdf["INVERSION_INDEX"] = (base - gdf["RIESGO_INDEX"] * PESO_RIESGO).clip(
        lower=0, upper=100
    )
    # NaN propagates through the subtraction on its own, so this is belt and
    # braces -- and it is the line that states the rule, which is worth having
    # explicitly rather than as a side effect of arithmetic.
    gdf.loc[~gdf["RIESGO_EVALUADO"], "INVERSION_INDEX"] = float("nan")

    sin_evaluar = int((~gdf["RIESGO_EVALUADO"]).sum())
    if sin_evaluar:
        print(
            f"  {sin_evaluar} AGEBs outside the flood Atlas: no index published "
            f"(30% of its weight was never measured there)."
        )

    return gdf


def exportar_capa_indice_inversion(gdf_inversion: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Export the Investment Index layer to data/, ready for Leaflet."""
    columnas_finales = [
        "CVEGEO",
        "NOM_MUN",
        "COLONIA",
        "SERVICIOS_INDEX",
        "SCORE_ESCUELA",
        "SCORE_SALUD",
        "SCORE_SUPERMERCADO",
        "COMERCIOS_INDEX",
        "RIESGO_INDEX",
        # Travels with the data on purpose: the card cannot tell "assessed and
        # found clear" from "never assessed" by looking at a null RIESGO_INDEX
        # alone, and those two mean opposite things to a buyer.
        "RIESGO_EVALUADO",
        "INVERSION_INDEX",
        "MOTIVO_SIN_DATO",
        "geometry",
    ]
    # With no service data there is no index: 40% of its weight is missing, so
    # INVERSION_INDEX ends up null by NaN propagation. They are kept in the
    # layer to paint them gray and explain the reason, rather than letting an
    # unmeasured AGEB look like a bad investment. The same rule now covers the
    # flood term (30%): a sector outside the Atlas is grey too, because the
    # missing penalty could only flatter it and the colour ramp would have
    # ranked it against sectors that did pay one.
    gdf_final = gdf_inversion[columnas_finales].copy()
    gdf_final["geometry"] = gdf_final["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    salida = DATA_DIR / "indice_inversion.geojson"
    gdf_final.to_file(salida, driver="GeoJSON")

    tamano_kb = salida.stat().st_size / 1024
    print(f"\nFinal layer exported: {salida} ({len(gdf_final)} AGEBs, {tamano_kb:.1f} KB)")
    return gdf_final


def exportar_capa_servicios_basicos(gdf_ageb_servicios: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepare and export the final Basic Services layer to data/, ready for
    Leaflet: only the columns relevant to the frontend and simplified geometry
    to keep the file lightweight.
    """
    columnas_finales = [
        "CVEGEO",
        "NOM_MUN",
        "COLONIA",
        "POBTOT",
        "TVIVHAB",
        "PCT_ELECTRICIDAD",
        "PCT_AGUA",
        "PCT_DRENAJE",
        "PCT_INTERNET",
        "SERVICIOS_INDEX",
        "MOTIVO_SIN_DATO",
        "geometry",
    ]
    # AGEBs with no data are kept on purpose (with a null SERVICIOS_INDEX and
    # their MOTIVO_SIN_DATO): the map paints them gray and explains why. They
    # used to be dropped with dropna, so they simply vanished from the map
    # without anyone knowing they existed.
    gdf_final = gdf_ageb_servicios[columnas_finales].copy()
    gdf_final["geometry"] = gdf_final["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    salida = DATA_DIR / "servicios_basicos.geojson"
    gdf_final.to_file(salida, driver="GeoJSON")

    tamano_kb = salida.stat().st_size / 1024
    print(f"\nFinal layer exported: {salida} ({len(gdf_final)} AGEBs, {tamano_kb:.1f} KB)")
    return gdf_final


def descargar_raster_inundacion(bounds_4326: tuple[float, float, float, float]) -> bool:
    """
    Download the ANRI flood Severity layer (Tr=100 years) from CONAGUA as a
    semi-transparent georeferenced PNG and save its metadata.

    Args:
        bounds_4326: extent (minx, miny, maxx, maxy) in EPSG:4326 that the PNG
            must cover; normally the AGEB extent plus a margin.

    Returns:
        True if the download succeeded; False if it failed (e.g. no
        connection), so the rest of the (offline) pipeline is not interrupted.

    Alignment notes: the PNG is rendered in Web Mercator (EPSG:3857) over
    exactly the corners of the given bbox. Leaflet `imageOverlay` stretches the
    image linearly over the Mercator projection of those same corners, so the
    layer stays aligned with the base map with no vertical distortion.
    """
    minx, miny, maxx, maxy = bounds_4326
    minx -= ANRI_MARGEN_GRADOS
    miny -= ANRI_MARGEN_GRADOS
    maxx += ANRI_MARGEN_GRADOS
    maxy += ANRI_MARGEN_GRADOS

    # Size proportional to the Web Mercator extent (~square pixels).
    transformador = Transformer.from_crs(4326, 3857, always_xy=True)
    x0, y0 = transformador.transform(minx, miny)
    x1, y1 = transformador.transform(maxx, maxy)
    aspecto = (x1 - x0) / (y1 - y0)
    ancho_px = max(1, round(ANRI_ALTO_PX * aspecto))

    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": 4326,
        "imageSR": 3857,
        "size": f"{ancho_px},{ANRI_ALTO_PX}",
        "format": "png32",
        "transparent": "true",
        "dpi": 96,
        "layers": f"show:{ANRI_CAPA_SEVERIDAD_TR100}",
        "f": "image",
    }
    url = f"{ANRI_MAPSERVER}/export?{urllib.parse.urlencode(params)}"

    print("Downloading flood layer (ANRI - CONAGUA)...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "geo-riesgos-saltillo"})
        # `url` is a CONAGUA HTTPS constant (ANRI_MAPSERVER), not user input:
        # there is no file:/ scheme or dynamic URL. That is why B310 is silenced.
        with urllib.request.urlopen(req, timeout=90) as resp:  # nosec B310
            contenido = resp.read()
    except Exception as exc:  # noqa: BLE001 - the download is optional/offline-safe
        print(f"  Notice: could not download the flood raster ({exc}).")
        print("  Skipping the flood layer; the rest of the pipeline continues.")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RIESGO_INUNDACION_PNG.write_bytes(contenido)

    # Bounds in the order Leaflet expects: [[south, west], [north, east]].
    meta = {
        "fuente": ANRI_FUENTE,
        "fecha_descarga": date.today().isoformat(),
        "url_servicio": f"{ANRI_MAPSERVER}/{ANRI_CAPA_SEVERIDAD_TR100}",
        "periodo_retorno_anios": 100,
        "variable": "Severidad (índice compuesto de tirante y velocidad)",
        "nota": (
            "Raster oficial de CONAGUA (ANRI). Clases: severidad alta (rojo), "
            "media (amarillo) y baja (verde). Aproximación por modelación "
            "hidráulica; no sustituye un estudio de sitio."
        ),
        "bounds": [[miny, minx], [maxy, maxx]],
    }
    RIESGO_INUNDACION_META.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    tamano_kb = RIESGO_INUNDACION_PNG.stat().st_size / 1024
    print(
        f"  Flood layer saved: {RIESGO_INUNDACION_PNG} "
        f"({ancho_px}x{ANRI_ALTO_PX} px, {tamano_kb:.1f} KB) + metadata."
    )
    return True


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    gdf_agebs = filtrar_agebs_por_municipio()

    salida = PROCESSED_DIR / "ageb_filtrado.geojson"
    gdf_agebs.to_file(salida, driver="GeoJSON")
    print(f"\nSaved (intermediate, not the final layer): {salida}")

    print("\nProcessing basic-services data from the 2020 Census...")
    df_censo = cargar_censo_servicios()
    df_servicios = calcular_cobertura_servicios(df_censo)

    print("Deriving colonia name per AGEB (Frente de manzana layer)...")
    df_colonias = cargar_nombres_colonias()

    print("\nBuilding the street index (Frente de manzana layer)...")
    exportar_indice_calles(construir_indice_calles())

    gdf_ageb_servicios = integrar_censo_a_ageb(gdf_agebs, df_servicios, df_colonias)

    salida_servicios = PROCESSED_DIR / "ageb_con_servicios.geojson"
    gdf_ageb_servicios.to_file(salida_servicios, driver="GeoJSON")
    print(f"Saved (intermediate, not the final layer): {salida_servicios}")

    exportar_capa_servicios_basicos(gdf_ageb_servicios)

    print("\nReading cadastral land values (Tesorería Municipal, 2026)...")
    catastro_valores, catastro_colonias = extraer_tablas_catastrales()
    exportar_valor_catastral(asignar_valor_catastral(
        gdf_ageb_servicios, catastro_valores, catastro_colonias))

    print("\nProcessing IMPLAN risk layers (CARTO SALTILLO, 2024 Atlas)...")
    # Kept unfiltered as well: the published layer drops "Muy bajo", but a cell
    # in that class WAS assessed, so the full mesh -- not the visible zones --
    # is what says which AGEBs the model looked at.
    gdf_inundacion_completa = cargar_riesgo_implan(IMPLAN_INUNDACION_SHP, "Intensid_1")
    gdf_inundacion = preparar_capa_riesgo(gdf_inundacion_completa)
    exportar_capa_riesgo(
        gdf_inundacion, RIESGO_INUNDACION_GEOJSON,
        "Riesgo por Inundaciones Pluviales", "Hidrometeorológico",
    )
    gdf_deslizamientos = preparar_capa_riesgo(
        cargar_riesgo_implan(IMPLAN_DESLIZAMIENTOS_SHP, "Intensid_1")
    )
    exportar_capa_riesgo(
        gdf_deslizamientos, RIESGO_DESLIZAMIENTOS_GEOJSON,
        "Riesgo por Deslizamientos Traslacionales", "Geológico",
    )
    # Chemical-technological risk: highly relevant along the Saltillo–Ramos
    # Arizpe industrial corridor. Own threshold (Medio+Alto): see
    # NIVELES_ELEVADOS_QUIMICO. Informational-only layer (does not penalize the
    # index, like landslides; only flood penalizes).
    gdf_quimico = preparar_capa_riesgo(
        cargar_riesgo_implan(IMPLAN_QUIMICO_SHP, "Intensid_1"),
        niveles=NIVELES_ELEVADOS_QUIMICO,
    )
    exportar_capa_riesgo(
        gdf_quimico, RIESGO_QUIMICO_GEOJSON,
        "Riesgo Químico-Tecnológico", "Químico-Tecnológico",
    )

    print("\nComputing flood exposure per AGEB (penalty)...")
    df_riesgo = calcular_riesgo_inundacion_por_ageb(
        gdf_agebs, gdf_inundacion, gdf_inundacion_completa
    )

    print("\nComputing Real-Estate Investment Index...")
    gdf_denue = cargar_denue()
    df_comercios = calcular_indice_comercios(gdf_agebs, gdf_denue)
    gdf_inversion = calcular_indice_inversion(gdf_ageb_servicios, df_comercios, df_riesgo)
    exportar_capa_indice_inversion(gdf_inversion)

    print("\nDownloading backup flood layer (ANRI - CONAGUA)...")
    minx, miny, maxx, maxy = gdf_agebs.total_bounds
    descargar_raster_inundacion((minx, miny, maxx, maxy))
