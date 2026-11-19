"""Measure the IMMUS 2026 public-transport layers against the 431 sectors.

Archived one-off analysis, not pipeline: nothing here feeds published data.
Run from the repository root, with raw_data/ in place:

    venv/bin/python scripts/immus/medir_transporte.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import process_data as P  # noqa: E402

CARPETA = Path("raw_data/immus")
RUTAS = CARPETA / "RUTAS_AQUI_VAMOS" / "RUTAS AQUI VAMOS G.shp"
PARADAS = CARPETA / "PARADAS_AQUI_VAMOS" / "PARADAS AQUI VAMOS.shp"
ALIMENTADORAS = CARPETA / "ALIMENTADORAS" / "ALIMENTADORAS.shp"
UMBRALES_KM = [0.5, 0.8, 1.0, 2.0]


def poblacion_publicada() -> pd.Series:
    with open("data/servicios_basicos.geojson", encoding="utf-8") as f:
        props = [x["properties"] for x in json.load(f)["features"]]
    return pd.DataFrame(props).set_index("CVEGEO")["POBTOT"]


def resumen_distancias(etiqueta: str, d: pd.Series, mun: pd.Series, pob: pd.Series) -> None:
    print(f"\n{etiqueta}: median {d.median():.2f} km")
    filas = []
    for nombre in ["Saltillo", "Ramos Arizpe", "Arteaga", None]:
        sel = d if nombre is None else d[mun == nombre]
        fila = {"municipio": nombre or "Total", "sectores": len(sel), "mediana_km": round(sel.median(), 2)}
        for u in UMBRALES_KM:
            dentro = sel[sel <= u].index
            fila[f"<= {u} km"] = len(dentro)
            total_pob = pob.reindex(sel.index).sum()
            fila[f"pob <= {u} km"] = f"{pob.reindex(dentro).sum() / total_pob:.0%}" if total_pob else "—"
        filas.append(fila)
    print(pd.DataFrame(filas).to_string(index=False))


def main() -> None:
    rutas = gpd.read_file(RUTAS)
    paradas = gpd.read_file(PARADAS)
    alim = gpd.read_file(ALIMENTADORAS)

    # One record per trunk carries the route name and a no-data point (-1.8e308) instead of a stop.
    sin_punto = paradas.geometry.x.abs().gt(180) | paradas.geometry.y.abs().gt(90)
    print(f"Records: {len(paradas)}, with a no-data point: {int(sin_punto.sum())}")
    print(paradas[sin_punto].drop(columns=["geometry", "path"]).to_string())
    paradas = paradas[~sin_punto].copy()
    coords = paradas.geometry.apply(lambda g: (round(g.x, 6), round(g.y, 6)))
    print(f"Stops with a valid point: {len(paradas)}, distinct positions: {coords.nunique()}")
    print(paradas["TRONCAL"].value_counts().to_string())
    print(f"Without VIALIDAD: {int(paradas['VIALIDAD'].isna().sum())}")

    m_rutas = rutas.to_crs(P.CRS_METRICO)
    m_alim = alim.to_crs(P.CRS_METRICO)
    print("\nTrunk routes (km):")
    print(m_rutas.assign(km=m_rutas.length / 1000)[["NOMBRE", "TRONCAL", "km"]].round(1).to_string(index=False))
    print("Feeder routes (km):")
    print(m_alim.assign(km=m_alim.length / 1000)[["NOMBRE", "CODIGO", "Código", "km"]].round(1).to_string(index=False))

    agebs = P.filtrar_agebs_por_municipio()
    m_agebs = agebs[["CVEGEO", "NOM_MUN", "geometry"]].to_crs(P.CRS_METRICO)
    m_paradas = paradas.to_crs(P.CRS_METRICO)

    en_ageb = gpd.sjoin(m_paradas, m_agebs, predicate="within", how="left")
    print("\nStops by municipality of the sector they fall in (NaN = outside every sector):")
    print(en_ageb["NOM_MUN"].value_counts(dropna=False).to_string())
    print(f"Sectors with at least one stop inside: {en_ageb['CVEGEO'].nunique()}")

    lineas = pd.concat([m_rutas[["geometry"]], m_alim[["geometry"]]], ignore_index=True)
    toca = gpd.sjoin(m_agebs, gpd.GeoDataFrame(lineas, crs=P.CRS_METRICO), predicate="intersects")
    print(f"Sectors crossed by a trunk or feeder route: {toca['CVEGEO'].nunique()}")

    centroides = m_agebs.copy()
    centroides["geometry"] = centroides.geometry.centroid
    mun = centroides.set_index("CVEGEO")["NOM_MUN"]
    pob = poblacion_publicada()

    j = gpd.sjoin_nearest(centroides, m_paradas[["geometry"]], distance_col="d")
    d_parada = j.groupby("CVEGEO")["d"].min() / 1000
    resumen_distancias("Centroid to nearest trunk stop", d_parada, mun, pob)

    j = gpd.sjoin_nearest(centroides, gpd.GeoDataFrame(lineas, crs=P.CRS_METRICO), distance_col="d")
    d_linea = j.groupby("CVEGEO")["d"].min() / 1000
    resumen_distancias("Centroid to nearest trunk or feeder line", d_linea, mun, pob)


if __name__ == "__main__":
    main()
