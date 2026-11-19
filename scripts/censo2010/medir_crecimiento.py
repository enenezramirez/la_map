"""Measure how comparable the 2010 and 2020 Census AGEBs are, and what changed.

Archived one-off analysis, not pipeline: nothing here feeds published data.
Run from the repository root, with raw_data/ in place:

    venv/bin/python scripts/censo2010/medir_crecimiento.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import process_data as P  # noqa: E402

CARPETA = Path("raw_data/inegi_censo2010")
AGEB_2010 = CARPETA / "mgau2010v5_0" / "AGEB_urb_2010_5.shp"
CENSO_2010 = CARPETA / "resageburb" / "RESAGEBURB_05DBF10.dbf"
PREFIJOS = ("05030", "05027", "05004")
COLUMNAS = ["VIVTOT", "TVIVHAB", "VIVPAR_DES", "POBTOT"]
UMBRALES_IOU = [0.90, 0.95, 0.98]
UMBRAL_IOU = 0.95


def tabla_ageb(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    df = df[(df["MZA"] == "000") & (df["AGEB"] != "0000")].copy()
    df["CVEGEO"] = df["ENTIDAD"] + df["MUN"] + df["LOC"] + df["AGEB"]
    df = df[df["CVEGEO"].str.startswith(PREFIJOS)]
    enmascarados = {c: int((~df[c].astype(str).str.fullmatch(r"\d+")).sum()) for c in COLUMNAS}
    for c in COLUMNAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("CVEGEO")[COLUMNAS], enmascarados


def main() -> None:
    a20 = P.filtrar_agebs_por_municipio()[["CVEGEO", "NOM_MUN", "geometry"]].to_crs(P.CRS_METRICO)
    a10 = gpd.read_file(AGEB_2010, where="substr(CVEGEO,1,5) IN ('05030','05027','05004')")
    print(f"2010 vector: FECHAACT {a10['FECHAACT'].value_counts().to_dict()}")
    a10 = a10[["CVEGEO", "geometry"]].to_crs(P.CRS_METRICO)
    a10["geometry"] = a10.geometry.make_valid()
    a20["geometry"] = a20.geometry.make_valid()
    mun = a20.set_index("CVEGEO")["NOM_MUN"]

    k10, k20 = set(a10["CVEGEO"]), set(a20["CVEGEO"])
    print(f"\nAGEBs: 2010 {len(k10)}, 2020 {len(k20)}; same key {len(k10 & k20)}, "
          f"only 2020 {len(k20 - k10)}, only 2010 {len(k10 - k20)}")

    comunes = sorted(k10 & k20)
    g10 = a10.set_index("CVEGEO").loc[comunes, "geometry"]
    g20 = a20.set_index("CVEGEO").loc[comunes, "geometry"]
    iou = g10.intersection(g20, align=True).area / g10.union(g20, align=True).area
    print("\nSame key, intersection over union of the two polygons:")
    print(f"  median {iou.median():.3f}, 10th percentile {iou.quantile(0.1):.3f}")
    for u in UMBRALES_IOU:
        print(f"  IoU >= {u}: {int((iou >= u).sum())} of {len(iou)}")
    estables = iou[iou >= UMBRAL_IOU].index

    nuevos = a20[~a20["CVEGEO"].isin(k10)]
    huella10 = a10.union_all()
    dentro = nuevos.geometry.intersection(huella10).area / nuevos.area
    print(f"\n2020-only AGEBs ({len(nuevos)}): share of their area that was urban AGEB in 2010")
    print(f"  under 10%: {int((dentro < 0.1).sum())}, 10-90%: {int(((dentro >= 0.1) & (dentro <= 0.9)).sum())}, "
          f"over 90%: {int((dentro > 0.9).sum())}")
    print(nuevos.assign(dentro=dentro.values)["NOM_MUN"].value_counts().to_string())

    t10, m10 = tabla_ageb(gpd.read_file(CENSO_2010, ignore_geometry=True).astype(str))
    df20 = pd.concat(
        [pd.read_csv(P.censo_csv(e), dtype=str, low_memory=False) for e in ["05"]], ignore_index=True
    )
    t20, m20 = tabla_ageb(df20)
    print(f"\nNon-numeric (masked) AGEB values, 2010: {m10}; 2020: {m20}")

    grupos = P.agrupar_agebs_entre_censos(a10, a20)
    por_grupo = grupos.groupby("grupo")["censo"].agg(lambda s: (int((s == '10').sum()), int((s == '20').sum())))
    tipos = por_grupo.map(lambda t: "1:1" if t == (1, 1) else ("new" if t[0] == 0 else ("gone" if t[1] == 0 else "n:m")))
    print(f"\nComparable groups: {len(por_grupo)}")
    print(tipos.value_counts().to_string())
    sectores_1a1 = grupos[(grupos["censo"] == "20") & grupos["grupo"].map(tipos).eq("1:1")]["CVEGEO"]
    print(f"2020 sectors in a 1:1 group: {len(sectores_1a1)}; of them same key and IoU >= {UMBRAL_IOU}: "
          f"{len(set(sectores_1a1) & set(estables))}")

    filas = []
    for (gid, sub) in grupos.groupby("grupo"):
        c10 = sub.loc[sub["censo"] == "10", "CVEGEO"]
        c20 = sub.loc[sub["censo"] == "20", "CVEGEO"]
        v10 = t10.reindex(c10)
        v20 = t20.reindex(c20)
        fila = {"grupo": gid, "tipo": tipos[gid], "n20": len(c20),
                "municipio": mun.reindex(c20).mode().iat[0] if len(c20) else None}
        for c in COLUMNAS:
            fila[f"{c}_10"] = v10[c].sum(min_count=1) if len(c10) else 0
            fila[f"{c}_20"] = v20[c].sum(min_count=1) if len(c20) else 0
            fila[f"{c}_falta"] = bool(v10[c].isna().any() or v20[c].isna().any())
        filas.append(fila)
    res = pd.DataFrame(filas)

    print("\nTotals over the three municipalities' urban AGEBs:")
    for c in COLUMNAS:
        print(f"  {c}: 2010 {t10[c].sum():,.0f} -> 2020 {t20.reindex(list(k20))[c].sum():,.0f}")

    comp = res[res["n20"] > 0].copy()
    comp["dviv"] = comp["VIVTOT_20"] - comp["VIVTOT_10"]
    comp["crec"] = comp["dviv"] / comp["VIVTOT_10"].where(comp["VIVTOT_10"] > 0)
    print("\nGroups with 2020 sectors, change in total dwellings (VIVTOT):")
    print(comp.groupby("tipo").agg(grupos=("grupo", "size"), sectores=("n20", "sum"),
                                   viv10=("VIVTOT_10", "sum"), viv20=("VIVTOT_20", "sum")).to_string())
    print("Growth in 1:1 groups:")
    q = comp.loc[comp["tipo"] == "1:1", "crec"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
    print(q.round(3).to_string())
    for etiqueta, sel in [("lost dwellings", comp["dviv"] < 0), ("grew 0-25%", comp["crec"].between(0, 0.25)),
                          ("grew >100%", comp["crec"] > 1)]:
        print(f"  groups that {etiqueta}: {int(sel.sum())}")

    comp["des10"] = comp["VIVPAR_DES_10"] / comp["VIVTOT_10"].where(comp["VIVTOT_10"] > 0)
    comp["des20"] = comp["VIVPAR_DES_20"] / comp["VIVTOT_20"].where(comp["VIVTOT_20"] > 0)
    print("\nShare of uninhabited private dwellings (VIVPAR_DES / VIVTOT), groups with dwellings both years:")
    ambos = comp.dropna(subset=["des10", "des20"])
    print(f"  groups {len(ambos)}; median 2010 {ambos['des10'].median():.3f}, 2020 {ambos['des20'].median():.3f}")
    print(f"  rose by more than 5 points: {int((ambos['des20'] - ambos['des10'] > 0.05).sum())}, "
          f"fell by more than 5 points: {int((ambos['des10'] - ambos['des20'] > 0.05).sum())}")


if __name__ == "__main__":
    main()
