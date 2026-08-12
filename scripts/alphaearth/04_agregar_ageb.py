"""Aggregate the 160 m embedding overview to the 431 AGEBs.

Step 3 of the screening in DATOS.md 3.6: a 431 x 64 table, each row the mean of
the embedding pixels falling in that AGEB, renormalized to the unit sphere
(a mean of unit vectors is not itself a unit vector).

The AGEB is the unit this app publishes every number in, and 3.6's "what NOT to
do" list is explicit that validating at pixel level and reporting at AGEB level
is how 18.72 M "samples" turn into a confidence nobody earned. So the pixel
count behind each row is carried along and reported: a row backed by two pixels
is not the same evidence as one backed by fifty, and the screening has to be
able to say so.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "raw_data" / "alphaearth"
NPZ = DATOS / "aef_overview_2024.npz"
CAPA = RAIZ / "data" / "servicios_basicos.geojson"
SALIDA = DATOS / "aef_por_ageb_2024.npz"
EPSG_ZONA = 32614


def dequantizar(bruto: np.ndarray) -> np.ndarray:
    v = bruto.astype(np.float64)
    return ((v / 127.5) ** 2) * np.sign(v)


def main() -> None:
    d = np.load(NPZ)
    bruto = d["bruto"]
    origen_e, origen_n, res = float(d["origen_e"]), float(d["origen_n"]), float(d["res"])
    _, alto, ancho = bruto.shape
    valores = dequantizar(bruto)                      # (64, alto, ancho)

    gdf = gpd.read_file(CAPA).to_crs(EPSG_ZONA)
    print(f"{len(gdf)} AGEBs, CRS {gdf.crs.to_string()}")
    print(f"rejilla {ancho}x{alto} px de {res:.0f} m desde E {origen_e:,.0f} N {origen_n:,.0f}")

    # Burn 1-based AGEB indices; 0 stays "no AGEB".
    transformacion = from_origin(origen_e, origen_n, res, res)
    etiquetas = rasterize(
        ((geom, i + 1) for i, geom in enumerate(gdf.geometry)),
        out_shape=(alto, ancho), transform=transformacion,
        fill=0, dtype=np.int32, all_touched=False,
    )
    print(f"pixeles asignados a algun AGEB: {(etiquetas > 0).sum():,}/{etiquetas.size:,}")

    tabla = np.zeros((len(gdf), 64), dtype=np.float64)
    conteo = np.zeros(len(gdf), dtype=np.int32)
    por_centroide = []

    planas = valores.reshape(64, -1)
    etiquetas_planas = etiquetas.ravel()
    for i in range(len(gdf)):
        sel = etiquetas_planas == (i + 1)
        n = int(sel.sum())
        conteo[i] = n
        if n:
            tabla[i] = planas[:, sel].mean(axis=1)
        else:
            # Smaller than a 160 m cell, or straddling cell centres: fall back
            # to the single pixel containing the centroid, and record that it
            # was a fallback rather than silently mixing the two cases.
            c = gdf.geometry.iloc[i].centroid
            col = int((c.x - origen_e) / res)
            fila = int((origen_n - c.y) / res)
            if 0 <= col < ancho and 0 <= fila < alto:
                tabla[i] = valores[:, fila, col]
                por_centroide.append(i)

    normas = np.linalg.norm(tabla, axis=1, keepdims=True)
    validas = normas[:, 0] > 0
    tabla[validas] /= normas[validas]

    print(f"\nAGEBs con pixeles propios: {(conteo > 0).sum()}")
    print(f"AGEBs resueltos por centroide (mas chicos que la celda): {len(por_centroide)}")
    print(f"AGEBs sin vector: {(~validas).sum()}")
    print(f"pixeles por AGEB -> min {conteo.min()}  mediana {int(np.median(conteo))}  "
          f"media {conteo.mean():.1f}  max {conteo.max()}")
    bajos = int((conteo[conteo > 0] < 5).sum())
    print(f"AGEBs con menos de 5 pixeles: {bajos} "
          f"({100 * bajos / len(gdf):.1f}%) -- evidencia mas delgada, se reporta")

    np.savez_compressed(
        SALIDA, tabla=tabla, conteo=conteo, validas=validas,
        cvegeo=gdf["CVEGEO"].to_numpy().astype("U16"),
        colonia=gdf["COLONIA"].to_numpy().astype("U64"),
        municipio=gdf["NOM_MUN"].to_numpy().astype("U32"),
    )
    print(f"\nguardado en {SALIDA} "
          f"({SALIDA.stat().st_size / 1024:.0f} KB, tabla {tabla.shape})")


if __name__ == "__main__":
    main()
