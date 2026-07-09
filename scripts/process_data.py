"""
GeoRiesgos Saltillo - Script de Procesamiento de Datos Espaciales
----------------------------------------------------------------
Fase 2, Tarea 1: Filtrar el Marco Geoestadístico (INEGI) para obtener
únicamente los polígonos de AGEB de los municipios de interés
(Saltillo, Ramos Arizpe, Arteaga).

Por ahora solo hay datos de AGEB descargados para Saltillo. La configuración
MUNICIPIOS_AGEB está lista para que, en cuanto se descarguen las localidades
de Ramos Arizpe y Arteaga (mismo formato de INEGI: carpeta por localidad con
conjunto_de_datos/<clave_localidad>a.shp), baste con agregar sus rutas aquí.

Fase 2, Tarea 2: Procesar los datos de servicios básicos del Censo de
Población y Vivienda 2020 (INEGI, nivel AGEB urbana) e integrarlos a los
polígonos de AGEB por CVEGEO.

Fase 2, Tarea 4: Exportar la capa de Servicios Básicos a GeoJSON limpio y
liviano en la carpeta data/, lista para que Leaflet la cargue directamente.
(La Tarea 3, cruce espacial con zonas de inundación de CENAPRED, queda
bloqueada por falta de una capa granular de inundación — ver task.md).

Extra: los AGEB no tienen nombre de colonia en el Marco Geoestadístico (son
unidades estadísticas, no coinciden 1 a 1 con una colonia). El nombre se
deriva de la capa "Frente de manzana" (fm), que sí trae el campo NOMASEN
(nombre de asentamiento) por cada frente de cuadra: se usa el NOMASEN más
frecuente entre los frentes de cada AGEB como aproximación de su colonia.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

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

# Variables del Censo 2020 usadas para el índice de cobertura de servicios
# básicos (ver SPEC.md). Se usan las variantes "positivas" (viviendas que SÍ
# disponen del servicio): VPH_AGUADV en vez de VPH_AGUAFV (que es la negativa).
COLUMNAS_SERVICIOS = ["VPH_C_ELEC", "VPH_AGUADV", "VPH_DRENAJ", "VPH_INTER"]

# Cada entrada mapea un municipio a las carpetas de localidad (INEGI) que
# contienen su capa de AGEB. Una localidad sin capa "a" (AGEB) —usual en
# localidades rurales pequeñas— simplemente no se incluye aquí.
MUNICIPIOS_AGEB: dict[str, list[Path]] = {
    "Saltillo": [
        RAW_DATA / "marco_geoestadistico" / "saltillo_map_ageb" / "050300001",
    ],
    "Ramos Arizpe": [
        # TODO: agregar aquí las carpetas de localidad de Ramos Arizpe
        # descargadas de INEGI (Marco Geoestadístico) cuando estén disponibles.
    ],
    "Arteaga": [
        # TODO: agregar aquí las carpetas de localidad de Arteaga
        # descargadas de INEGI (Marco Geoestadístico) cuando estén disponibles.
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


def filtrar_marco_geoestadistico() -> gpd.GeoDataFrame:
    """
    Combina los AGEB de todos los municipios configurados en MUNICIPIOS_AGEB
    en un único GeoDataFrame, reproyectado a EPSG:4326 (WGS84) para su uso
    directo en Leaflet.
    """
    print("Filtrando Marco Geoestadístico por municipio...")

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
    AGEB) y toma el NOMASEN más frecuente. Excluye "ND" (sin dato) salvo que
    sea el único valor disponible para ese AGEB.
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
        con_dato = grupo.loc[grupo["NOMASEN"] != "ND", "NOMASEN"]
        serie = con_dato if not con_dato.empty else grupo["NOMASEN"]
        return serie.value_counts().idxmax()

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

    columnas_numericas = ["POBTOT", "TVIVHAB", *COLUMNAS_SERVICIOS]
    for col in columnas_numericas:
        # INEGI enmascara conteos pequeños (1-2) con "*" por confidencialidad.
        # Se tratan como 0 viviendas: el impacto en el % de cobertura es
        # mínimo y evita descartar el AGEB completo del índice.
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df[["CVEGEO", "NOM_MUN", "POBTOT", "TVIVHAB", *COLUMNAS_SERVICIOS]]


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

    df["PCT_ELECTRICIDAD"] = (df["VPH_C_ELEC"] / tviv_seguro * 100).fillna(0)
    df["PCT_AGUA"] = (df["VPH_AGUADV"] / tviv_seguro * 100).fillna(0)
    df["PCT_DRENAJE"] = (df["VPH_DRENAJ"] / tviv_seguro * 100).fillna(0)
    df["PCT_INTERNET"] = (df["VPH_INTER"] / tviv_seguro * 100).fillna(0)

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
    ]
    gdf_unido = gdf_agebs.merge(df_servicios[columnas_censo], on="CVEGEO", how="left")
    gdf_unido = gdf_unido.merge(df_colonias, on="CVEGEO", how="left")
    gdf_unido["COLONIA"] = gdf_unido["COLONIA"].fillna("Sin nombre de colonia")

    sin_censo = gdf_unido["SERVICIOS_INDEX"].isna().sum()
    if sin_censo:
        print(f"  Aviso: {sin_censo} AGEB(s) sin datos de censo (probablemente no residenciales).")

    return gdf_unido


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
        "geometry",
    ]
    gdf_final = gdf_ageb_servicios[columnas_finales].copy()
    gdf_final = gdf_final.dropna(subset=["SERVICIOS_INDEX"])
    gdf_final["geometry"] = gdf_final["geometry"].simplify(
        TOLERANCIA_SIMPLIFICACION, preserve_topology=True
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    salida = DATA_DIR / "servicios_basicos.geojson"
    gdf_final.to_file(salida, driver="GeoJSON")

    tamano_kb = salida.stat().st_size / 1024
    print(f"\nCapa final exportada: {salida} ({len(gdf_final)} AGEBs, {tamano_kb:.1f} KB)")
    return gdf_final


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    gdf_agebs = filtrar_marco_geoestadistico()

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
