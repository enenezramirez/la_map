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

Phase 5, Task 1: Real-Estate Investment Index (see formula in SPEC.md). The
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
import urllib.parse
import urllib.request
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
# Index (see SPEC.md). "escuela" and "salud" are identified by their SCIAN
# sector (the first two digits of codigo_act); "supermercado" has no sector of
# its own in SCIAN, so it is identified by business-activity name.
CATEGORIAS_DENUE = {
    "escuela": lambda df: df["codigo_act"].str.startswith("61"),
    "salud": lambda df: df["codigo_act"].str.startswith("62"),
    "supermercado": lambda df: df["nombre_act"].str.contains("supermercado", case=False, na=False),
}

# Investment Index weights (SPEC.md).
PESO_SERVICIOS = 0.4
PESO_COMERCIOS = 0.3
# Flood-risk penalty (SPEC.md). Applied as a subtraction on the base
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

# Traffic-light order of intensity and its 0-100 score for the penalty.
NIVELES_INTENSIDAD = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"]
PUNTAJE_INTENSIDAD = {"Muy bajo": 0, "Bajo": 25, "Medio": 50, "Alto": 75, "Muy alto": 100}
# Levels kept in the visible layers and in the penalty. "Muy bajo" is
# discarded (background of ~90-98% of the area, no risk value).
NIVELES_ELEVADOS = ["Bajo", "Medio", "Alto", "Muy alto"]
# Higher threshold for chemical-technological risk: there "Bajo" covers 93% of
# the grid (the model's background, no discriminating value) and, if kept, the
# layer alone would exceed SPEC.md §2's 5 MB limit (6.9 MB measured). With
# Medio+Alto it stays at ~1.2 MB, showing only the genuinely exposed zones.
NIVELES_ELEVADOS_QUIMICO = ["Medio", "Alto", "Muy alto"]

RIESGO_INUNDACION_GEOJSON = DATA_DIR / "riesgo_inundacion.geojson"
RIESGO_DESLIZAMIENTOS_GEOJSON = DATA_DIR / "riesgo_deslizamientos.geojson"
RIESGO_QUIMICO_GEOJSON = DATA_DIR / "riesgo_quimico.geojson"

# 2020 Census variables used for the basic-services coverage index (see
# SPEC.md). The "positive" variants are used (dwellings that DO have the
# service): VPH_AGUADV instead of VPH_AGUAFV (the negative one).
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


def cargar_nombres_colonias() -> pd.DataFrame:
    """
    Derive each AGEB's dominant colonia/settlement name from the "Frente de
    manzana" (fm) layer: group its records by AGEB (the first 13 characters of
    the front's CVEGEO match the AGEB's CVEGEO) and take the most frequent
    NOMASEN, ignoring INEGI's filler values (VALORES_SIN_ASENTAMIENTO). If an
    AGEB has no real name, it is labeled SIN_COLONIA instead of propagating the
    filler to the map.
    """
    registros = []
    for carpetas in MUNICIPIOS_AGEB.values():
        for carpeta in carpetas:
            clave_localidad = carpeta.name
            shp_path = carpeta / "conjunto_de_datos" / f"{clave_localidad}fm.shp"
            if not shp_path.exists():
                continue
            df_fm = gpd.read_file(shp_path, columns=["CVEGEO", "NOMASEN"], ignore_geometry=True)
            df_fm["CVEGEO"] = df_fm["CVEGEO"].str[:13]
            registros.append(df_fm)

    if not registros:
        return pd.DataFrame(columns=["CVEGEO", "COLONIA"])

    df_fm = pd.concat(registros, ignore_index=True)

    def _colonia_dominante(grupo: pd.DataFrame) -> str:
        nombres = grupo["NOMASEN"].astype(str).str.strip()
        con_dato = nombres[~nombres.str.upper().isin(VALORES_SIN_ASENTAMIENTO)]
        if con_dato.empty:
            return SIN_COLONIA
        return con_dato.value_counts().idxmax()

    colonias = df_fm.groupby("CVEGEO").apply(_colonia_dominante, include_groups=False)
    return colonias.rename("COLONIA").reset_index()


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
    the layer alone would exceed SPEC.md §2's 5 MB limit.
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
    zones, attach traceability metadata (SPEC.md §1.2: title, phenomenon,
    source and cutoff date) and export the risk layer to data/ ready for
    Leaflet.

    The `explode` is what lets a single zone highlight on the map when hovered,
    rather than every blotch of the same level across the city: with the
    dissolved multipolygon, Leaflet sees a single element per level. It does not
    alter the geometry (same shape, declared as several features); it only
    repeats the properties on each one, at a cost of about ~450 KB total across
    the two layers, well below SPEC.md §2's 5 MB limit.

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


def calcular_riesgo_inundacion_por_ageb(
    gdf_agebs: gpd.GeoDataFrame, gdf_inundacion: gpd.GeoDataFrame
) -> pd.DataFrame:
    """
    Compute RIESGO_INDEX (0-100) per AGEB as area-weighted flood exposure:
    sum(level_intersection_area × level_score) over the AGEB's total area. An
    AGEB with no intersection with elevated risk → 0. The computation is done
    in a metric CRS (EPSG:6372) for correct areas.
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
    return resultado[["CVEGEO", "RIESGO_INDEX"]]


def calcular_indice_inversion(
    gdf_ageb_servicios: gpd.GeoDataFrame,
    df_comercios: pd.DataFrame,
    df_riesgo: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """
    Compute the Real-Estate Investment Index (SPEC.md). The base index combines
    Services (0.4) and Comercios (0.3) renormalized to 0-100; on top of it the
    flood-Risk penalty (0.3) is applied, subtracting up to 30 points based on
    the AGEB's exposure. The result is clipped to [0, 100].
    """
    gdf = gdf_ageb_servicios.merge(df_comercios, on="CVEGEO", how="left")
    gdf = gdf.merge(df_riesgo, on="CVEGEO", how="left")
    gdf["RIESGO_INDEX"] = gdf["RIESGO_INDEX"].fillna(0)

    peso_base = PESO_SERVICIOS + PESO_COMERCIOS
    base = (
        gdf["SERVICIOS_INDEX"] * PESO_SERVICIOS + gdf["COMERCIOS_INDEX"] * PESO_COMERCIOS
    ) / peso_base
    gdf["INVERSION_INDEX"] = (base - gdf["RIESGO_INDEX"] * PESO_RIESGO).clip(lower=0, upper=100)

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
        "INVERSION_INDEX",
        "MOTIVO_SIN_DATO",
        "geometry",
    ]
    # With no service data there is no index: 40% of its weight is missing, so
    # INVERSION_INDEX ends up null by NaN propagation. They are kept in the
    # layer to paint them gray and explain the reason, rather than letting an
    # unmeasured AGEB look like a bad investment.
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

    gdf_ageb_servicios = integrar_censo_a_ageb(gdf_agebs, df_servicios, df_colonias)

    salida_servicios = PROCESSED_DIR / "ageb_con_servicios.geojson"
    gdf_ageb_servicios.to_file(salida_servicios, driver="GeoJSON")
    print(f"Saved (intermediate, not the final layer): {salida_servicios}")

    exportar_capa_servicios_basicos(gdf_ageb_servicios)

    print("\nProcessing IMPLAN risk layers (CARTO SALTILLO, 2024 Atlas)...")
    gdf_inundacion = preparar_capa_riesgo(
        cargar_riesgo_implan(IMPLAN_INUNDACION_SHP, "Intensid_1")
    )
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
    df_riesgo = calcular_riesgo_inundacion_por_ageb(gdf_agebs, gdf_inundacion)

    print("\nComputing Real-Estate Investment Index...")
    gdf_denue = cargar_denue()
    df_comercios = calcular_indice_comercios(gdf_agebs, gdf_denue)
    gdf_inversion = calcular_indice_inversion(gdf_ageb_servicios, df_comercios, df_riesgo)
    exportar_capa_indice_inversion(gdf_inversion)

    print("\nDownloading backup flood layer (ANRI - CONAGUA)...")
    minx, miny, maxx, maxy = gdf_agebs.total_bounds
    descargar_raster_inundacion((minx, miny, maxx, maxy))
