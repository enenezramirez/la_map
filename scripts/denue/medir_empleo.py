"""Re-derive the figures in DATOS.md 3.10 on nearness to employment.

Archived one-off analysis, not pipeline: nothing here feeds published data.
Run from the repository root, with raw_data/ in place:

    venv/bin/python scripts/denue/medir_empleo.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import process_data as P  # noqa: E402

MUNICIPIOS = ["030", "027", "004"]  # Saltillo, Ramos Arizpe, Arteaga
ESTRATOS_101 = ["101 a 250 personas", "251 y más personas"]
MANUFACTURA = ["31", "32", "33"]


def cargar() -> pd.DataFrame:
    columnas = ["codigo_act", "per_ocu", "tipoCenCom", "nom_CenCom", "cve_mun",
                "municipio", "latitud", "longitud"]
    df = pd.read_csv(P.denue_csv("05"), usecols=columnas, dtype=str, encoding="latin-1")
    df = df[df["cve_mun"].isin(MUNICIPIOS)].copy()
    df["sector"] = df["codigo_act"].str[:2]
    df["en_parque"] = df["tipoCenCom"].fillna("").str.contains("PARQUE INDUSTRIAL", case=False)
    df["industrial"] = df["tipoCenCom"].fillna("").str.contains("INDUSTRIAL", case=False)
    return df


def distancias(centroides: gpd.GeoDataFrame, puntos: gpd.GeoDataFrame) -> pd.Series:
    j = gpd.sjoin_nearest(centroides, puntos[["geometry"]], distance_col="d")
    return j.groupby("CVEGEO")["d"].min() / 1000


def main() -> None:
    df = cargar()
    print(f"Establishments in the three municipalities: {len(df)}")
    print(df["per_ocu"].value_counts().to_string())

    parque = df[df["en_parque"]]
    print(f"\nTagged 'PARQUE INDUSTRIAL': {len(parque)}, {parque['nom_CenCom'].nunique()} distinct names")
    g251 = df["per_ocu"].eq("251 y más personas")
    print(f"251+: {int(g251.sum())}, of them manufacturing: {int((g251 & df['sector'].isin(MANUFACTURA)).sum())}")
    print(f"251+ outside any declared industrial park or zone: {int((g251 & ~df['industrial']).sum())}")
    print(df[g251]["municipio"].value_counts().to_string())

    puntos = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitud"].astype(float), df["latitud"].astype(float)),
        crs=4326,
    ).to_crs(P.CRS_METRICO)
    agebs = P.filtrar_agebs_por_municipio()
    centroides = agebs[["CVEGEO", "NOM_MUN", "geometry"]].to_crs(P.CRS_METRICO)
    centroides["geometry"] = centroides.geometry.centroid

    for nombre, mascara in [
        ("251+", g251),
        ("101+", df["per_ocu"].isin(ESTRATOS_101)),
        ("101+ manufacturing", df["per_ocu"].isin(ESTRATOS_101) & df["sector"].isin(MANUFACTURA)),
        ("tagged industrial park", df["en_parque"]),
    ]:
        d = distancias(centroides, puntos[mascara.values])
        print(f"\nNearest {nombre} (n={int(mascara.sum())}), km from the sector centroid:")
        print("  quantiles:", d.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(2).to_dict())
        print("  within 1 / 2 / 3 km:", [int((d <= km).sum()) for km in (1, 2, 3)], f"of {len(d)}")

    zona = centroides.copy()
    zona["geometry"] = zona.geometry.buffer(5000)
    cuenta = gpd.sjoin(zona, puntos[g251.values][["geometry"]], predicate="contains")
    cuenta = cuenta.groupby("CVEGEO").size().reindex(centroides["CVEGEO"]).fillna(0)
    print("\n251+ establishments within 5 km, quantiles:",
          cuenta.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict())


if __name__ == "__main__":
    main()
