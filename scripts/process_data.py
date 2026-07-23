"""
Traza - Script de Procesamiento de Datos Espaciales
----------------------------------------------------------------
Fase 2, Tarea 1: Filtrar la capa de AGEB de INEGI para obtener únicamente los
polígonos de los municipios de interés (Saltillo, Ramos Arizpe, Arteaga).

La fuente de los AGEB es el producto "Información vectorial de localidades
amanzanadas y números exteriores 2023" de INEGI (NO el Marco Geoestadístico:
ese es solo una de sus capas base, edición diciembre 2022). La procedencia
completa de este y de los demás datasets está en DATOS.md.

Por ahora solo hay datos de AGEB descargados para Saltillo. La configuración
MUNICIPIOS_AGEB está lista para que, en cuanto se descarguen las localidades
de Ramos Arizpe y Arteaga (mismo formato de INEGI: carpeta por localidad con
conjunto_de_datos/<clave_localidad>a.shp), baste con agregar sus rutas aquí.

Fase 2, Tarea 2: Procesar los datos de servicios básicos del Censo de
Población y Vivienda 2020 (INEGI, nivel AGEB urbana) e integrarlos a los
polígonos de AGEB por CVEGEO.

Fase 2, Tarea 3: Cruce espacial de los AGEB con las zonas de inundación
(overlay vectorial contra las capas del IMPLAN, ver abajo). El dataset
municipal de CENAPRED se descartó por no tener granularidad intraurbana.

Fase 2, Tarea 4: Exportar la capa de Servicios Básicos a GeoJSON limpio y
liviano en la carpeta data/, lista para que Leaflet la cargue directamente.

Extra: los AGEB no tienen nombre de colonia propio (son unidades estadísticas,
no coinciden 1 a 1 con una colonia). El nombre se deriva de la capa "Frente de
manzana" (fm), que sí trae el campo NOMASEN
(nombre de asentamiento) por cada frente de cuadra: se usa el NOMASEN más
frecuente entre los frentes de cada AGEB como aproximación de su colonia.

Fase 5, Tarea 1: Índice de Inversión Inmobiliaria (fórmula definida abajo).
El componente de "Comercios" se calcula con el DENUE (escuelas, salud y
supermercados) como cercanía del centroide de cada AGEB al establecimiento
más próximo de cada categoría. El componente de "Riesgo" (peso 0.3) se
calcula como la exposición a inundación de cada AGEB (capas IMPLAN, abajo)
y se aplica como penalización sobre el índice base de Servicios+Comercios.

Fase 4, Tarea (capas de riesgo): las capas de riesgo provienen del Atlas de
Riesgos 2024 del IMPLAN Saltillo (plataforma CARTO SALTILLO), descargadas
como shapefiles vectoriales (EPSG:6372):
  - Riesgo por inundaciones pluviales urbanas (Capa 1).
  - Riesgo por deslizamientos traslacionales (Capa 4, geológico).
Cada capa trae un nivel de intensidad (Muy bajo→Muy alto). Se descarta el
nivel "Muy bajo" (cubre ~90-98% del área: es el fondo sin valor informativo
y agranda mucho el GeoJSON) y se disuelve por nivel para un archivo liviano.
Al ser vector, el cruce con los AGEB (para la penalización de riesgo del
Índice de Inversión) es un overlay espacial directo, sin dependencias nuevas.

Respaldo: se conserva la capa de inundación del ANRI de CONAGUA (raster PNG
georreferenciado, `descargar_raster_inundacion`) como fuente alternativa;
IMPLAN es la fuente primaria por ser local, vectorial y de 2024.
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

# Tolerancia de simplificación de geometría en grados (EPSG:4326). ~0.00005°
# equivale a ~5 m en Saltillo, suficiente para aligerar el GeoJSON sin
# deformar visiblemente los polígonos de AGEB a los niveles de zoom del mapa.
TOLERANCIA_SIMPLIFICACION = 0.00005

CENSO_CSV = (
    RAW_DATA
    / "ageb_mza_urbana_05_cpv2020_csv"
    / "ageb_mza_urbana_05_cpv2020"
    / "conjunto_de_datos"
    / "conjunto_de_datos_ageb_urbana_05_cpv2020.csv"
)

DENUE_CSV = RAW_DATA / "denue_05_csv" / "conjunto_de_datos" / "denue_inegi_05_.csv"

# Categorías de equipamiento urbano para el componente "Comercios" del Índice
# de Inversión. "escuela" y "salud" se identifican por su
# sector SCIAN (los dos primeros dígitos de codigo_act); "supermercado" no
# tiene un sector propio en SCIAN, así que se identifica por nombre de giro.
CATEGORIAS_DENUE = {
    "escuela": lambda df: df["codigo_act"].str.startswith("61"),
    "salud": lambda df: df["codigo_act"].str.startswith("62"),
    "supermercado": lambda df: df["nombre_act"].str.contains("supermercado", case=False, na=False),
}

# Pesos del Índice de Inversión.
PESO_SERVICIOS = 0.4
PESO_COMERCIOS = 0.3
# Penalización por riesgo de inundación. Se aplica como resta sobre
# el índice base de Servicios+Comercios (ver calcular_indice_inversion).
PESO_RIESGO = 0.3

# Distancia (km) más allá de la cual un establecimiento ya no suma puntos de
# cercanía. 3 km es un radio razonable de acceso en auto dentro de una ciudad
# del tamaño de Saltillo; decae linealmente hasta 0 en ese punto.
RADIO_MAX_KM = 3.0

# Valores de relleno del campo NOMASEN (nombre de asentamiento) en la capa de
# Frente de manzana de INEGI. No son nombres de colonia: "ND" es "no
# disponible" (su TIPOASEN también dice "ND") y "NINGUNO" marca los frentes sin
# asentamiento asignado. Hay que descartarlos antes de calcular el nombre más
# frecuente por AGEB: si no, un AGEB con 5 frentes "NINGUNO" y 4 con nombre
# real termina llamándose "NINGUNO" en el mapa. Ojo: no todo valor corto es
# relleno — "GIS" es real (Sector GIS, por Grupo Industrial Saltillo).
VALORES_SIN_ASENTAMIENTO = frozenset({"ND", "NINGUNO"})

# Rótulo para un AGEB sin ningún nombre de asentamiento real. Preferible a
# mostrar el valor de relleno crudo en la ficha del mapa.
SIN_COLONIA = "SIN NOMBRE REGISTRADO"

# CRS métrico (el mismo de la cartografía vectorial de INEGI) usado solo para
# calcular distancias en metros; la salida final se reproyecta a EPSG:4326.
CRS_METRICO = "EPSG:6372"

# --- Capa de Riesgo de Inundación (ANRI - CONAGUA) -------------------------
# Servicio ArcGIS REST público del Atlas Nacional de Riesgo por Inundación.
# La capa 142 es "Severidad, periodo de retorno 100 años" del grupo
# "Saltillo, Coahuila" (Región Noreste). Es un raster: se descarga como PNG
# georreferenciado para usarlo como imageOverlay en Leaflet.
ANRI_MAPSERVER = (
    "https://rmgir.proyectomesoamerica.org/server/rest/services/"
    "ANRI/RegionNoreste_ANRI/MapServer"
)
ANRI_CAPA_SEVERIDAD_TR100 = 142
ANRI_FUENTE = (
    "CONAGUA — Atlas Nacional de Riesgo por Inundación (ANRI), Región Noreste. "
    "Capa: Severidad, periodo de retorno 100 años (Saltillo, Coahuila)."
)
# Margen (en grados) alrededor de la extensión de los AGEB para no recortar
# los cauces de inundación que entran/salen de la mancha urbana.
ANRI_MARGEN_GRADOS = 0.03
# Alto del PNG en píxeles; el ancho se calcula proporcional a la extensión en
# Web Mercator para mantener los píxeles ~cuadrados y el archivo liviano.
ANRI_ALTO_PX = 1500

RIESGO_INUNDACION_PNG = DATA_DIR / "riesgo_inundacion.png"
RIESGO_INUNDACION_META = DATA_DIR / "riesgo_inundacion_meta.json"

# --- Capas de riesgo IMPLAN (CARTO SALTILLO - Atlas de Riesgos 2024) --------
# Fuente primaria (vectorial, local, 2024). Shapefiles en EPSG:6372.
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

# Orden semafórico de intensidad y su puntaje 0-100 para la penalización.
NIVELES_INTENSIDAD = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"]
PUNTAJE_INTENSIDAD = {"Muy bajo": 0, "Bajo": 25, "Medio": 50, "Alto": 75, "Muy alto": 100}
# Niveles que se conservan en las capas visibles y en la penalización. Se
# descarta "Muy bajo" (fondo del ~90-98% del área, sin valor de riesgo).
NIVELES_ELEVADOS = ["Bajo", "Medio", "Alto", "Muy alto"]
# Umbral más alto para el riesgo químico-tecnológico: ahí "Bajo" cubre el 93%
# de la malla (el fondo del modelo, sin valor discriminante) y, conservándolo,
# la capa rebasaría sola el límite de 5 MB del proyecto (6.9 MB medidos). Con
# Medio+Alto queda en ~1.2 MB mostrando solo las zonas genuinamente expuestas.
NIVELES_ELEVADOS_QUIMICO = ["Medio", "Alto", "Muy alto"]

RIESGO_INUNDACION_GEOJSON = DATA_DIR / "riesgo_inundacion.geojson"
RIESGO_DESLIZAMIENTOS_GEOJSON = DATA_DIR / "riesgo_deslizamientos.geojson"
RIESGO_QUIMICO_GEOJSON = DATA_DIR / "riesgo_quimico.geojson"

# Variables del Censo 2020 usadas para el índice de cobertura de servicios
# básicos. Se usan las variantes "positivas" (viviendas que SÍ
# disponen del servicio): VPH_AGUADV en vez de VPH_AGUAFV (que es la negativa).
COLUMNAS_SERVICIOS = ["VPH_C_ELEC", "VPH_AGUADV", "VPH_DRENAJ", "VPH_INTER"]

# Cada entrada mapea un municipio a las carpetas de localidad (INEGI) que
# contienen su capa de AGEB. Una localidad sin capa "a" (AGEB) —usual en
# localidades rurales pequeñas— simplemente no se incluye aquí.
MUNICIPIOS_AGEB: dict[str, list[Path]] = {
    "Saltillo": [
        RAW_DATA / "marco_geoestadistico" / "saltillo_map_ageb" / "050300001",
    ],
    # Rutas pre-cableadas: el pipeline las omite con gracia mientras no exista la
    # carpeta (imprime "se omite" y sigue), y las toma en cuanto se descarguen de
    # INEGI (mismo producto que Saltillo, ver DATOS.md §2.1). Las claves de
    # localidad se verificaron contra el Censo 2020 de Coahuila: Ramos Arizpe es
    # el municipio 027 (no 025), Arteaga el 004.
    "Ramos Arizpe": [
        RAW_DATA / "marco_geoestadistico" / "ramos_arizpe_map_ageb" / "050270001",  # Ramos Arizpe (ciudad)
    ],
    "Arteaga": [
        RAW_DATA / "marco_geoestadistico" / "arteaga_map_ageb" / "050040001",  # Arteaga (cabecera)
        RAW_DATA / "marco_geoestadistico" / "arteaga_map_ageb" / "050040107",  # San Antonio de las Alazanas (sierra)
    ],
}


def cargar_ageb_municipio(nombre_municipio: str, carpetas_localidad: list[Path]) -> gpd.GeoDataFrame | None:
    """Carga y combina las capas de AGEB de todas las localidades disponibles de un municipio."""
    if not carpetas_localidad:
        print(f"  [{nombre_municipio}] Sin datos AGEB descargados todavía, se omite.")
        return None

    capas = []
    for carpeta in carpetas_localidad:
        clave_localidad = carpeta.name
        shp_path = carpeta / "conjunto_de_datos" / f"{clave_localidad}a.shp"
        if not shp_path.exists():
            print(f"  [{nombre_municipio}] No se encontró {shp_path}, se omite localidad {clave_localidad}.")
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
    Combina los AGEB de todos los municipios configurados en MUNICIPIOS_AGEB
    en un único GeoDataFrame, reproyectado a EPSG:4326 (WGS84) para su uso
    directo en Leaflet.
    """
    print("Filtrando AGEBs por municipio...")

    capas_municipio = []
    for nombre_municipio, carpetas in MUNICIPIOS_AGEB.items():
        gdf = cargar_ageb_municipio(nombre_municipio, carpetas)
        if gdf is not None:
            print(f"  [{nombre_municipio}] {len(gdf)} AGEBs cargados.")
            capas_municipio.append(gdf)

    if not capas_municipio:
        raise RuntimeError("No se cargó ningún AGEB. Verifica las rutas en MUNICIPIOS_AGEB.")

    gdf_final = pd.concat(capas_municipio, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs=capas_municipio[0].crs)
    gdf_final = gdf_final.to_crs(epsg=4326)

    print(f"\nTotal combinado: {len(gdf_final)} AGEBs en {gdf_final['NOM_MUN'].nunique()} municipio(s).")
    return gdf_final


def cargar_nombres_colonias() -> pd.DataFrame:
    """
    Deriva el nombre de colonia/asentamiento dominante de cada AGEB a partir
    de la capa "Frente de manzana" (fm): agrupa sus registros por AGEB (los
    primeros 13 caracteres del CVEGEO de frente coinciden con el CVEGEO de
    AGEB) y toma el NOMASEN más frecuente, ignorando los valores de relleno de
    INEGI (VALORES_SIN_ASENTAMIENTO). Si un AGEB no tiene ningún nombre real,
    se rotula con SIN_COLONIA en vez de propagar el relleno al mapa.
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
    Carga el CSV del Censo 2020 por AGEB urbana (todo Coahuila) y filtra
    únicamente las filas a nivel AGEB (excluye totales de entidad/municipio/
    localidad y el detalle por manzana) de los municipios en MUNICIPIOS_AGEB.
    """
    df = pd.read_csv(CENSO_CSV, dtype=str, low_memory=False)

    filas_ageb = (df["MZA"] == "000") & (df["AGEB"] != "0000")
    df = df[filas_ageb].copy()
    df = df[df["NOM_MUN"].isin(MUNICIPIOS_AGEB.keys())]

    df["CVEGEO"] = df["ENTIDAD"] + df["MUN"] + df["LOC"] + df["AGEB"]

    # POBTOT y TVIVHAB no vienen enmascarados en estos municipios (verificado:
    # 0 asteriscos), así que un valor no numérico aquí sí es un 0 real.
    for col in ["POBTOT", "TVIVHAB"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # INEGI enmascara conteos pequeños (1-2 viviendas) con "*" por
    # confidencialidad. NO se rellenan con 0 aquí: "enmascarado" y "cero" son
    # cosas distintas y confundirlas hacía que un AGEB sin dato publicado se
    # pintara como si tuviera 0% de cobertura. La distinción se resuelve en
    # calcular_cobertura_servicios(), que sí puede ver cuántas de las cuatro
    # columnas faltan.
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
    Calcula el % de viviendas con cada servicio básico y un índice compuesto
    (SERVICIOS_INDEX) como el promedio de los cuatro. El Censo agregado a
    nivel AGEB solo da totales por servicio, no la combinación conjunta real
    por vivienda, así que este promedio es la mejor aproximación disponible
    a "% de viviendas con servicios completos" sin usar microdatos.
    """
    df = df_censo.copy()
    tviv_seguro = df["TVIVHAB"].astype(float).replace(0, np.nan)

    # Un AGEB no tiene dato de cobertura cuando (a) no hay viviendas que servir
    # o (b) INEGI enmascaró las CUATRO columnas de servicios. En ambos casos el
    # índice queda en NaN y el frontend lo pinta como "sin datos" en gris, en
    # vez de mentir con un 0% que se leería como la peor cobertura de la ciudad.
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

    # Enmascarado parcial (1-3 de 4 columnas): sí es calculable. El asterisco
    # significa 1-2 viviendas sobre un total mucho mayor, así que tratar esa
    # columna como 0% se aproxima a la realidad en vez de tirar el AGEB entero.
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
    """Une los polígonos de AGEB con las variables de servicios del Censo y el nombre de colonia, por CVEGEO."""
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

    # Un AGEB que ni siquiera aparece en el Censo es un tercer caso de "sin
    # dato" y merece su propia explicación en la ficha.
    sin_registro = gdf_unido["SERVICIOS_INDEX"].isna() & gdf_unido["MOTIVO_SIN_DATO"].isna()
    gdf_unido.loc[sin_registro, "MOTIVO_SIN_DATO"] = "Sin registro en el Censo 2020"

    sin_dato = gdf_unido["SERVICIOS_INDEX"].isna().sum()
    if sin_dato:
        print(f"  Aviso: {sin_dato} AGEB(s) sin dato de servicios. Desglose:")
        for motivo, n in gdf_unido["MOTIVO_SIN_DATO"].value_counts().items():
            print(f"    - {motivo}: {n}")

    return gdf_unido


def cargar_denue() -> gpd.GeoDataFrame:
    """
    Carga el DENUE (todo Coahuila), lo filtra a los municipios configurados
    y clasifica cada establecimiento en una categoría de equipamiento urbano
    (escuela, salud, supermercado) según CATEGORIAS_DENUE.
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
    print(f"  DENUE: {len(gdf)} establecimientos relevantes ({gdf['CATEGORIA'].value_counts().to_dict()}).")
    return gdf


def calcular_indice_comercios(gdf_agebs: gpd.GeoDataFrame, gdf_denue: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Para cada AGEB, calcula un puntaje 0-100 de cercanía a cada categoría de
    equipamiento urbano (distancia del centroide del AGEB al establecimiento
    más próximo, con decaimiento lineal hasta RADIO_MAX_KM) y los promedia en
    COMERCIOS_INDEX.
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
        # sjoin_nearest puede producir más de un match por empate de distancia;
        # nos quedamos con la distancia mínima por AGEB.
        distancia_km = cercano.groupby("CVEGEO")["DIST_M"].min() / 1000
        score = (100 * (1 - distancia_km / RADIO_MAX_KM)).clip(lower=0)
        resultado[columna_score] = resultado["CVEGEO"].map(score).fillna(0)

    resultado["COMERCIOS_INDEX"] = resultado[columnas_score].mean(axis=1)
    return resultado


def cargar_riesgo_implan(shp_path: Path, campo_intensidad: str) -> gpd.GeoDataFrame:
    """
    Carga un shapefile de riesgo del IMPLAN (CARTO SALTILLO), normaliza el
    nivel de intensidad a la escala estándar (Muy bajo→Muy alto) y reproyecta
    a EPSG:4326 para el frontend. Devuelve todos los polígonos (sin filtrar).
    """
    gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
    # Los shapefiles usan distinta capitalización ("Muy alto" vs "muy bajo");
    # se normaliza a la forma "Xxxx xxxx".
    gdf["INTENSIDAD"] = gdf[campo_intensidad].str.strip().str.capitalize()
    return gdf


def preparar_capa_riesgo(
    gdf_riesgo: gpd.GeoDataFrame, niveles: list[str] = NIVELES_ELEVADOS
) -> gpd.GeoDataFrame:
    """
    Filtra a los niveles de riesgo relevantes y disuelve por nivel de
    intensidad, produciendo un GeoDataFrame liviano (un multipolígono por
    nivel), ordenado de menor a mayor intensidad, con el puntaje 0-100 de cada
    nivel. Esta geometría alimenta tanto la penalización del Índice de Inversión
    como la capa visible (que además la separa en zonas al exportarla, ver
    `exportar_capa_riesgo`), garantizando consistencia.

    `niveles` es el umbral de qué niveles se conservan; por defecto
    `NIVELES_ELEVADOS` (descarta solo "Muy bajo", el fondo del ~90-98% del
    área). Una capa puede pasar un umbral más alto: p. ej. el riesgo
    químico-tecnológico descarta también "Bajo" porque ahí ese nivel cubre el
    93% de la malla (el fondo del modelo, sin valor discriminante) y, sin
    recortarlo, la capa rebasaría por sí sola el límite de 5 MB del proyecto.
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
    Simplifica la geometría, separa el multipolígono de cada nivel en sus zonas
    individuales, adjunta metadatos de trazabilidad (título,
    fenómeno, fuente y fecha de corte) y exporta la capa de riesgo a data/
    lista para Leaflet.

    El `explode` es lo que permite que, al señalar una zona en el mapa, se
    resalte solo esa y no todas las manchas del mismo nivel en la ciudad: con
    el multipolígono disuelto, Leaflet ve un único elemento por nivel. No altera
    la geometría (es la misma figura, declarada como varias features); solo
    repite las propiedades en cada una, a un costo de unos ~450 KB en total
    entre las dos capas, muy por debajo del límite de 5 MB del proyecto.

    Se explota aquí y no en `preparar_capa_riesgo` a propósito: la versión
    disuelta sigue alimentando la penalización del Índice de Inversión, donde
    tener una sola geometría por nivel es lo natural para el overlay.
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
        f"  Capa de riesgo exportada: {salida} "
        f"({niveles} niveles, {len(gdf)} zonas, {tamano_kb:.1f} KB)"
    )
    return gdf


def calcular_riesgo_inundacion_por_ageb(
    gdf_agebs: gpd.GeoDataFrame, gdf_inundacion: gpd.GeoDataFrame
) -> pd.DataFrame:
    """
    Calcula RIESGO_INDEX (0-100) por AGEB como la exposición a inundación
    ponderada por área: suma(área_intersección_nivel × puntaje_nivel) sobre el
    área total del AGEB. Un AGEB sin intersección con riesgo elevado → 0.
    El cálculo se hace en CRS métrico (EPSG:6372) para áreas correctas.
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
    Calcula el Índice de Inversión Inmobiliaria. El índice base
    combina Servicios (0.4) y Comercios (0.3) renormalizado a 0-100; sobre él
    se aplica la penalización por Riesgo de inundación (0.3), que resta hasta
    30 puntos según la exposición del AGEB. El resultado se recorta a [0, 100].
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
    """Exporta la capa del Índice de Inversión a data/, lista para Leaflet."""
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
    # Sin dato de servicios no hay índice: falta el 40% de su peso, así que
    # INVERSION_INDEX queda nulo por propagación de NaN. Se conservan en la
    # capa para pintarlos en gris y explicar el motivo, en vez de dejar que
    # un AGEB no medido se vea como una mala inversión.
    gdf_final = gdf_inversion[columnas_finales].copy()
    gdf_final["geometry"] = gdf_final["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    salida = DATA_DIR / "indice_inversion.geojson"
    gdf_final.to_file(salida, driver="GeoJSON")

    tamano_kb = salida.stat().st_size / 1024
    print(f"\nCapa final exportada: {salida} ({len(gdf_final)} AGEBs, {tamano_kb:.1f} KB)")
    return gdf_final


def exportar_capa_servicios_basicos(gdf_ageb_servicios: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepara y exporta la capa final de Servicios Básicos a data/, lista para
    Leaflet: solo las columnas relevantes para el frontend y geometría
    simplificada para mantener el archivo liviano.
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
    # Los AGEBs sin dato se conservan a propósito (con SERVICIOS_INDEX nulo y
    # su MOTIVO_SIN_DATO): el mapa los pinta en gris y explica por qué. Antes
    # se descartaban con dropna, así que simplemente desaparecían del mapa sin
    # que nadie supiera que existían.
    gdf_final = gdf_ageb_servicios[columnas_finales].copy()
    gdf_final["geometry"] = gdf_final["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    salida = DATA_DIR / "servicios_basicos.geojson"
    gdf_final.to_file(salida, driver="GeoJSON")

    tamano_kb = salida.stat().st_size / 1024
    print(f"\nCapa final exportada: {salida} ({len(gdf_final)} AGEBs, {tamano_kb:.1f} KB)")
    return gdf_final


def descargar_raster_inundacion(bounds_4326: tuple[float, float, float, float]) -> bool:
    """
    Descarga la capa de Severidad de inundación (Tr=100 años) del ANRI de
    CONAGUA como PNG georreferenciado semitransparente y guarda sus metadatos.

    Args:
        bounds_4326: extensión (minx, miny, maxx, maxy) en EPSG:4326 que debe
            cubrir el PNG; normalmente la extensión de los AGEB más un margen.

    Returns:
        True si la descarga fue exitosa; False si falló (p. ej. sin conexión),
        para que el resto del pipeline (offline) no se interrumpa.

    Notas de alineación: el PNG se renderiza en Web Mercator (EPSG:3857) sobre
    exactamente las esquinas del bbox indicado. Leaflet `imageOverlay` estira
    la imagen linealmente sobre la proyección Mercator de esas mismas esquinas,
    por lo que la capa queda alineada con el mapa base sin distorsión vertical.
    """
    minx, miny, maxx, maxy = bounds_4326
    minx -= ANRI_MARGEN_GRADOS
    miny -= ANRI_MARGEN_GRADOS
    maxx += ANRI_MARGEN_GRADOS
    maxy += ANRI_MARGEN_GRADOS

    # Tamaño proporcional a la extensión en Web Mercator (píxeles ~cuadrados).
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

    print("Descargando capa de inundación (ANRI - CONAGUA)...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "geo-riesgos-saltillo"})
        # `url` es una constante HTTPS de CONAGUA (ANRI_MAPSERVER), no entrada del
        # usuario: no hay esquema file:/ ni URL dinámica. Por eso se silencia B310.
        with urllib.request.urlopen(req, timeout=90) as resp:  # nosec B310
            contenido = resp.read()
    except Exception as exc:  # noqa: BLE001 - la descarga es opcional/offline-safe
        print(f"  Aviso: no se pudo descargar el raster de inundación ({exc}).")
        print("  Se omite la capa de inundación; el resto del pipeline continúa.")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RIESGO_INUNDACION_PNG.write_bytes(contenido)

    # Bounds en el orden que espera Leaflet: [[sur, oeste], [norte, este]].
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
        f"  Capa de inundación guardada: {RIESGO_INUNDACION_PNG} "
        f"({ancho_px}x{ANRI_ALTO_PX} px, {tamano_kb:.1f} KB) + metadatos."
    )
    return True


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    gdf_agebs = filtrar_agebs_por_municipio()

    salida = PROCESSED_DIR / "ageb_filtrado.geojson"
    gdf_agebs.to_file(salida, driver="GeoJSON")
    print(f"\nGuardado (intermedio, no es la capa final): {salida}")

    print("\nProcesando datos de servicios del Censo 2020...")
    df_censo = cargar_censo_servicios()
    df_servicios = calcular_cobertura_servicios(df_censo)

    print("Derivando nombre de colonia por AGEB (capa Frente de manzana)...")
    df_colonias = cargar_nombres_colonias()

    gdf_ageb_servicios = integrar_censo_a_ageb(gdf_agebs, df_servicios, df_colonias)

    salida_servicios = PROCESSED_DIR / "ageb_con_servicios.geojson"
    gdf_ageb_servicios.to_file(salida_servicios, driver="GeoJSON")
    print(f"Guardado (intermedio, no es la capa final): {salida_servicios}")

    exportar_capa_servicios_basicos(gdf_ageb_servicios)

    print("\nProcesando capas de riesgo IMPLAN (CARTO SALTILLO, Atlas 2024)...")
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
    # Riesgo químico-tecnológico: muy relevante en el corredor industrial
    # Saltillo–Ramos Arizpe. Umbral propio (Medio+Alto): ver
    # NIVELES_ELEVADOS_QUIMICO. Capa solo informativa (no penaliza el índice,
    # igual que deslizamientos; solo la inundación penaliza).
    gdf_quimico = preparar_capa_riesgo(
        cargar_riesgo_implan(IMPLAN_QUIMICO_SHP, "Intensid_1"),
        niveles=NIVELES_ELEVADOS_QUIMICO,
    )
    exportar_capa_riesgo(
        gdf_quimico, RIESGO_QUIMICO_GEOJSON,
        "Riesgo Químico-Tecnológico", "Químico-Tecnológico",
    )

    print("\nCalculando exposición a inundación por AGEB (penalización)...")
    df_riesgo = calcular_riesgo_inundacion_por_ageb(gdf_agebs, gdf_inundacion)

    print("\nCalculando Índice de Inversión Inmobiliaria...")
    gdf_denue = cargar_denue()
    df_comercios = calcular_indice_comercios(gdf_agebs, gdf_denue)
    gdf_inversion = calcular_indice_inversion(gdf_ageb_servicios, df_comercios, df_riesgo)
    exportar_capa_indice_inversion(gdf_inversion)

    print("\nDescargando capa de inundación de respaldo (ANRI - CONAGUA)...")
    minx, miny, maxx, maxy = gdf_agebs.total_bounds
    descargar_raster_inundacion((minx, miny, maxx, maxy))
