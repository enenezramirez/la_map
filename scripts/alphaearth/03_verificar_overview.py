"""Check the downloaded overview before drawing a single conclusion from it.

DATOS.md 3.6 fixed this check in advance: "overview pixels are averaged
embeddings, and a mean of unit vectors is not itself unit-norm, so renormalize
and confirm against a full-resolution sample before drawing any conclusion."

The mirror README claims the producer already renormalized each overview pixel
to length 1. That is a claim by the data provider, which is exactly the kind of
thing this project verifies rather than repeats. Two tests here:

  A. Do the de-quantized overview vectors actually have length 1?
  B. Does an overview pixel agree with the full-resolution pixels beneath it --
     i.e. is it the right place, and the renormalized mean it claims to be?

Test B doubles as the georeferencing check: if the bottom-up flip had leaked
through anywhere, the overview pixel would match a MIRRORED location instead.
"""

from __future__ import annotations

import os

os.environ.update({
    "AWS_NO_SIGN_REQUEST": "YES",
    "AWS_REGION": "us-west-2",
    "AWS_DEFAULT_REGION": "us-west-2",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "2",
})

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

DATOS = Path(__file__).resolve().parents[2] / "raw_data" / "alphaearth"
NPZ = DATOS / "aef_overview_2024.npz"
BASE = ("/vsicurl/https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/"
        "tge-labs/aef/v1/annual/2024/14N/")
TESELA_OESTE = "xluefwwtrb3tded2n-0000000000-0000008192.vrt"
FACTOR = 16


def dequantizar(bruto: np.ndarray) -> np.ndarray:
    v = bruto.astype(np.float64)
    return ((v / 127.5) ** 2) * np.sign(v)


def main() -> None:
    d = np.load(NPZ)
    bruto, cubierto = d["bruto"], d["cubierto"]
    origen_e, origen_n, res = float(d["origen_e"]), float(d["origen_n"]), float(d["res"])
    bandas, alto, ancho = bruto.shape

    print(f"mosaico: {ancho} x {alto} px de {res:.0f} m, {bandas} bandas")
    print(f"origen (esquina NO): E {origen_e:,.0f}  N {origen_n:,.0f}")
    print(f"cobertura: {cubierto.sum():,}/{cubierto.size:,} px ({100 * cubierto.mean():.1f}%)")

    sin_dato = (bruto == -128).all(axis=0)
    validos = cubierto & ~sin_dato
    print(f"NoData: {sin_dato.sum():,} px  |  validos: {validos.sum():,} px")

    # -- Test A: unit norm ---------------------------------------------------
    valores = dequantizar(bruto)
    normas = np.linalg.norm(valores, axis=0)
    n = normas[validos]
    print("\n=== A. norma de los vectores de overview (deben ser 1) ===")
    print(f"  media {n.mean():.6f}  min {n.min():.6f}  max {n.max():.6f}")
    print(f"  peor desviacion |n-1| = {np.abs(n - 1).max():.6f}")
    print(f"  veredicto: {'UNITARIOS' if np.abs(n - 1).max() < 0.02 else 'NO UNITARIOS -> renormalizar'}")

    # -- Test B: agreement with full resolution ------------------------------
    # Pick a valid pixel comfortably inside the western tile.
    ys, xs = np.where(validos[:, :200])
    iy, ix = int(ys[len(ys) // 2]), int(xs[len(xs) // 2])
    e_px = origen_e + (ix + 0.5) * res
    n_px = origen_n - (iy + 0.5) * res
    print(f"\n=== B. contraste contra resolucion plena ===")
    print(f"  pixel de overview [{iy},{ix}] -> centro E {e_px:,.0f} N {n_px:,.0f}")

    with rasterio.open(BASE + TESELA_OESTE) as ds:
        # A raise, not an assert: `python -O` strips asserts, and this is the
        # guard against the bottom-up storage -- the one failure mode here that
        # yields a plausible wrong answer rather than an error.
        if ds.bounds.top <= ds.bounds.bottom:
            raise RuntimeError(f"{TESELA_OESTE}: vino bottom-up, no north-up")
        col = int((e_px - ds.bounds.left) / ds.res[0])
        fila = int((ds.bounds.top - n_px) / ds.res[1])
        c0, f0 = (col // FACTOR) * FACTOR, (fila // FACTOR) * FACTOR
        plena = ds.read(window=Window(c0, f0, FACTOR, FACTOR))
        print(f"  leidos {FACTOR}x{FACTOR} px a 10 m bajo ese pixel "
              f"(cols {c0}..{c0 + FACTOR}, filas {f0}..{f0 + FACTOR})")

    validos_plena = ~(plena == -128).all(axis=0)
    vf = dequantizar(plena)[:, validos_plena]
    print(f"  subpixeles validos: {validos_plena.sum()}/{FACTOR * FACTOR}")
    print(f"  norma media a resolucion plena: {np.linalg.norm(vf, axis=0).mean():.6f}")

    media = vf.mean(axis=1)
    media_norm = media / np.linalg.norm(media)
    ov = valores[:, iy, ix]
    ov_norm = ov / np.linalg.norm(ov)
    coseno = float(np.dot(media_norm, ov_norm))
    print(f"  coseno( overview , media renormalizada de los 10 m ) = {coseno:.6f}")

    # Control: the same overview pixel against the vertically mirrored location.
    with rasterio.open(BASE + TESELA_OESTE) as ds:
        f_espejo = ds.height - f0 - FACTOR
        espejo = ds.read(window=Window(c0, f_espejo, FACTOR, FACTOR))
    ve = dequantizar(espejo)
    ve = ve[:, ~(espejo == -128).all(axis=0)]
    if ve.shape[1]:
        me = ve.mean(axis=1)
        me /= np.linalg.norm(me)
        print(f"  CONTROL coseno contra la posicion ESPEJEADA = {float(np.dot(me, ov_norm)):.6f}")
        print("  (debe ser claramente menor; si fuera igual de alto, la prueba no discrimina)")

    ok = coseno > 0.98
    print(f"\n  veredicto B: {'COINCIDE' if ok else 'NO COINCIDE -> revisar georreferencia'}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
