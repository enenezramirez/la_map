"""Read the 160 m overview of the AlphaEarth embeddings over the project extent.

Step 2 of the screening approved in DATOS.md 3.6: read a COG overview rather
than full resolution -- ~4.7 MB instead of the 1.20 GB a full-resolution year
over this extent would cost.

Two corrections to what 3.6 assumed, both from the mirror's own README and both
verified here rather than taken on faith:

* The COGs are stored bottom-up, so the .tiff's own georeferencing comes back
  with north and south SWAPPED. Confirmed by opening both: the .tiff reports
  N=2,785,280 S=2,867,200 while its .vrt reports the correct N=2,867,200
  S=2,785,280. Everything here goes through the .vrt, and the code asserts the
  orientation rather than trusting it.
* De-quantization is NOT the linear rescale 3.6 described. The documented
  mapping is ((v/127.5)**2) * sign(v) -- squared, sign-preserving. A linear
  rescale would leave vectors off the unit sphere and quietly distort every
  cosine similarity computed downstream.

The VRTs reference their sources as /vsis3/, so anonymous S3 access has to be
enabled or GDAL retries without credentials until it gives up.
"""

from __future__ import annotations

import os

os.environ.update({
    "AWS_NO_SIGN_REQUEST": "YES",
    "AWS_REGION": "us-west-2",
    "AWS_DEFAULT_REGION": "us-west-2",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "2",
    "GDAL_HTTP_RETRY_DELAY": "1",
})

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

BASE = ("/vsicurl/https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/"
        "tge-labs/aef/v1/annual/{anio}/14N/")
TESELAS = [
    "xluefwwtrb3tded2n-0000000000-0000008192.vrt",
    "xv02dgpwlop8vtx30-0000000000-0000000000.vrt",
]

# Project extent in EPSG:32614, from aef_localizar.py.
BBOX_UTM = (291_837.0, 2_795_673.0, 342_246.0, 2_833_098.0)
NIVEL_OVERVIEW = 3      # 0-based into [2,4,8,16,...]; 3 -> factor 16
FACTOR = 16
RES = 10.0 * FACTOR     # 160 m
# raw_data/ is gitignored: these are intermediates, not published layers.
SALIDA_DIR = Path(__file__).resolve().parents[2] / "raw_data" / "alphaearth"
SALIDA = SALIDA_DIR / "aef_overview_2024.npz"


def exigir_north_up(ds, nombre: str) -> None:
    """Refuse to read a dataset whose rows run south-to-north.

    This is the guard against the mirror's bottom-up storage. It is a raise and
    not an assert on purpose: `python -O` strips asserts, and an orientation
    check that can be compiled away is not a check -- it would let the flipped
    read through silently, which is the one failure here that produces a
    plausible-looking wrong answer instead of an error.
    """
    if ds.bounds.top <= ds.bounds.bottom:
        raise RuntimeError(
            f"{nombre}: bounds N={ds.bounds.top:,.0f} <= S={ds.bounds.bottom:,.0f}. "
            "El dataset vino bottom-up; hay que leer el .vrt, no el .tiff."
        )


def dequantizar(bruto: np.ndarray) -> np.ndarray:
    """Map int8 codes to the documented -1..1 embedding values.

    Squared and sign-preserving, per the mirror README -- not a linear rescale.
    """
    v = bruto.astype(np.float32)
    return ((v / 127.5) ** 2) * np.sign(v)


def main(anio: int = 2024) -> None:
    base = BASE.format(anio=anio)
    oeste, sur, este, norte = BBOX_UTM

    # A global 160 m grid anchored on the western tile's top-left corner, so
    # both tiles land on the same lattice and the mosaic cannot be off by a
    # pixel where they meet.
    with rasterio.open(base + TESELAS[0], OVERVIEW_LEVEL=NIVEL_OVERVIEW) as ds0:
        exigir_north_up(ds0, TESELAS[0])
        if abs(ds0.res[0] - RES) > 1e-6:
            raise RuntimeError(f"resolucion inesperada {ds0.res}, se esperaba {RES} m")
        e0, n0 = ds0.bounds.left, ds0.bounds.top

    col_min = int(np.floor((oeste - e0) / RES))
    col_max = int(np.ceil((este - e0) / RES))
    fila_min = int(np.floor((n0 - norte) / RES))
    fila_max = int(np.ceil((n0 - sur) / RES))
    ancho, alto = col_max - col_min, fila_max - fila_min
    print(f"rejilla destino: {ancho} x {alto} px de {RES:.0f} m "
          f"({ancho * alto:,} px, {ancho * alto * 64 / 2**20:.2f} MB en int8)")

    mosaico = np.full((64, alto, ancho), -128, dtype=np.int8)
    cubierto = np.zeros((alto, ancho), dtype=bool)

    for nombre in TESELAS:
        t0 = time.time()
        with rasterio.open(base + nombre, OVERVIEW_LEVEL=NIVEL_OVERVIEW) as ds:
            exigir_north_up(ds, nombre)
            # Offset of this tile's grid within the global one.
            dcol = int(round((ds.bounds.left - e0) / RES))
            dfila = int(round((n0 - ds.bounds.top) / RES))

            c0 = max(col_min, dcol)
            c1 = min(col_max, dcol + ds.width)
            f0 = max(fila_min, dfila)
            f1 = min(fila_max, dfila + ds.height)
            if c1 <= c0 or f1 <= f0:
                print(f"  {nombre.split('-')[0]}: sin solape, se omite")
                continue

            ventana = Window(c0 - dcol, f0 - dfila, c1 - c0, f1 - f0)
            datos = ds.read(window=ventana)
            mosaico[:, f0 - fila_min:f1 - fila_min, c0 - col_min:c1 - col_min] = datos
            cubierto[f0 - fila_min:f1 - fila_min, c0 - col_min:c1 - col_min] = True
            print(f"  {nombre.split('-')[0]}: ventana {datos.shape[2]}x{datos.shape[1]} px "
                  f"en {time.time() - t0:.1f}s")

    print(f"\ncobertura del mosaico: {cubierto.sum():,}/{cubierto.size:,} px "
          f"({100 * cubierto.mean():.1f}%)")

    # NoData is -128 in every band at once, per the README.
    sin_dato = (mosaico == -128).all(axis=0)
    print(f"pixeles NoData: {sin_dato.sum():,} ({100 * sin_dato.mean():.2f}%)")

    valores = dequantizar(mosaico)
    normas = np.linalg.norm(valores, axis=0)
    validos = ~sin_dato & cubierto
    print(f"\n=== comprobacion de norma unitaria sobre {validos.sum():,} px validos ===")
    print(f"  media {normas[validos].mean():.6f}   min {normas[validos].min():.6f}   "
          f"max {normas[validos].max():.6f}")
    print(f"  desviacion respecto a 1: max |n-1| = {np.abs(normas[validos] - 1).max():.6f}")

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        SALIDA,
        bruto=mosaico, cubierto=cubierto,
        origen_e=e0 + col_min * RES, origen_n=n0 - fila_min * RES, res=RES,
    )
    print(f"\nguardado en {SALIDA} ({SALIDA.stat().st_size / 2**20:.2f} MB)")


if __name__ == "__main__":
    main()
    # GDAL's curl threads keep the interpreter alive, so the process is killed
    # rather than left hanging. os._exit skips the atexit flush, which on the
    # first run swallowed every line printed above -- flush explicitly first.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
