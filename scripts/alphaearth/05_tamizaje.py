"""Step 4 of the DATOS.md 3.6 screening: two questions, cosine similarity only.

The decision rule was fixed BEFORE running, and is quoted from 3.6:

  (a) do zones we already know to be different separate?
      -> "If (a) fails, the pipeline is wrong."
  (b) are the flooded colonias closer to each other than a random sample of the
      same size?
      -> "If (b) fails, use 1 dies cheaply."

Nothing is trained. Every number below is a dot product between unit vectors.

Two design choices that matter, both forced by the data rather than preferred:

* (b) runs at COLONIA level, not AGEB level. The labels are colonia-granular
  (a newspaper named colonias), and ZONA CENTRO alone spans 21 AGEBs -- letting
  it contribute 21 rows would let the historic core's own land-cover coherence
  masquerade as a flood signal.
* (a) uses the three municipios plus the historic core as its known-different
  groups. 3.6 suggested the "GIS industrial sector", but no colonia in the
  published layer is named GIS -- the name never won the mode in any AGEB -- so
  hand-picking a substitute would be choosing the anchor after seeing the data.
  Municipio is assigned by INEGI, independent of anything measured here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

NPZ = Path(__file__).resolve().parents[2] / "raw_data" / "alphaearth" / "aef_por_ageb_2024.npz"
SEMILLA = 20260811
N_PERMUTACIONES = 20_000
UMBRAL_P = 0.05  # fixed in DATOS.md 3.6 before any data was read

# The colonias Vanguardia named (DATOS.md 2.4). Only 8 of the 16 are recorded
# by name in this repo; the entry says "and others". Resolved against the
# published COLONIA values, which is why two carry their full registered name.
INUNDADAS = {
    "OMEGA": "OMEGA",
    "TERRANOVA": "TERRANOVA",
    "LOMAS DEL REFUGIO": "LOMAS DEL REFUGIO",
    "VALENCIA": "VALENCIA",
    "ZONA CENTRO": "ZONA CENTRO",
    "COUNTRY CLUB": "RESIDENCIAL COUNTRY CLUB",
    "LA AURORA": "LA AURORA I",
    "NAZARIO ORTIZ GARZA": None,  # no such colonia in the published layer
}


def normalizar(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v), where=n > 0)


def cohesion(vectores: np.ndarray) -> float:
    """Mean pairwise cosine within a group (excluding self-pairs)."""
    if len(vectores) < 2:
        return float("nan")
    g = vectores @ vectores.T
    n = len(vectores)
    return float((g.sum() - np.trace(g)) / (n * (n - 1)))


def entre(a: np.ndarray, b: np.ndarray) -> float:
    return float((a @ b.T).mean())


def main() -> None:
    d = np.load(NPZ)
    tabla, municipio, colonia = d["tabla"], d["municipio"], d["colonia"]
    conteo = d["conteo"]
    print(f"tabla {tabla.shape}, {len(np.unique(colonia))} colonias distintas")
    print(f"norma media de las filas: {np.linalg.norm(tabla, axis=1).mean():.6f}")

    rng = np.random.default_rng(SEMILLA)

    # ---------------------------------------------------------------- (a) ---
    print("\n" + "=" * 72)
    print("(a) ¿SE SEPARAN ZONAS QUE YA SABEMOS DISTINTAS?")
    print("=" * 72)

    grupos: dict[str, np.ndarray] = {}
    for m in ["Arteaga", "Ramos Arizpe", "Saltillo"]:
        grupos[m] = tabla[municipio == m]
    es_centro = colonia == "ZONA CENTRO"
    grupos["ZONA CENTRO"] = tabla[es_centro]
    grupos["Saltillo sin centro"] = tabla[(municipio == "Saltillo") & ~es_centro]

    print(f"\n{'grupo':<22}{'n':>5}{'cohesion interna':>20}")
    for k, v in grupos.items():
        print(f"{k:<22}{len(v):>5}{cohesion(v):>20.4f}")

    print(f"\n{'par':<42}{'entre grupos':>14}{'brecha':>10}")
    pares = [
        ("Arteaga", "Saltillo sin centro"),
        ("Ramos Arizpe", "Saltillo sin centro"),
        ("Arteaga", "Ramos Arizpe"),
        ("ZONA CENTRO", "Saltillo sin centro"),
    ]
    for x, y in pares:
        e = entre(grupos[x], grupos[y])
        interna = (cohesion(grupos[x]) + cohesion(grupos[y])) / 2
        print(f"{x + '  vs  ' + y:<42}{e:>14.4f}{interna - e:>10.4f}")

    # Discriminating control: random groups of the same sizes must show no gap.
    print("\ncontrol: particiones ALEATORIAS de los mismos tamaños")
    for x, y in [("Arteaga", "Saltillo sin centro"), ("ZONA CENTRO", "Saltillo sin centro")]:
        nx, ny = len(grupos[x]), len(grupos[y])
        brechas = []
        for _ in range(200):
            idx = rng.permutation(len(tabla))
            a, b = tabla[idx[:nx]], tabla[idx[nx:nx + ny]]
            brechas.append((cohesion(a) + cohesion(b)) / 2 - entre(a, b))
        print(f"  tamaños {nx:>3} vs {ny:>3}: brecha aleatoria "
              f"{np.mean(brechas):+.4f} ± {np.std(brechas):.4f}")

    # ---------------------------------------------------------------- (b) ---
    print("\n" + "=" * 72)
    print("(b) ¿SE PARECEN ENTRE SÍ LAS COLONIAS INUNDADAS?")
    print("=" * 72)

    # Colonia-level table: mean of its AGEBs, renormalized.
    nombres = np.unique(colonia)
    perfiles = np.vstack([normalizar(tabla[colonia == c].mean(axis=0)) for c in nombres])
    agebs_por_colonia = np.array([int((colonia == c).sum()) for c in nombres])
    print(f"perfiles por colonia: {perfiles.shape}")

    print("\nresolución de las colonias nombradas en DATOS.md §2.4:")
    positivas = []
    for citada, publicada in INUNDADAS.items():
        if publicada is None or publicada not in set(nombres.tolist()):
            print(f"  {citada:<22} -> SIN CORRESPONDENCIA en la capa publicada")
            continue
        i = int(np.where(nombres == publicada)[0][0])
        positivas.append(i)
        etiqueta = f"(publicada como «{publicada}»)" if publicada != citada else ""
        print(f"  {citada:<22} -> {agebs_por_colonia[i]:>2} AGEBs  {etiqueta}")

    pos = perfiles[positivas]
    k = len(positivas)
    observada = cohesion(pos)
    print(f"\npositivos utilizables: {k} de las 16 que reportó la nota "
          f"({k / 16:.0%} del conjunto real)")
    print(f"cohesión observada del conjunto inundado: {observada:.4f}")

    nulo = np.empty(N_PERMUTACIONES)
    for i in range(N_PERMUTACIONES):
        nulo[i] = cohesion(perfiles[rng.choice(len(perfiles), k, replace=False)])
    p = float((nulo >= observada).mean())
    print(f"nulo por muestreo aleatorio de {k} colonias ({N_PERMUTACIONES:,} sorteos):")
    print(f"  media {nulo.mean():.4f}   sd {nulo.std():.4f}   "
          f"p95 {np.quantile(nulo, 0.95):.4f}")
    print(f"  p(cohesión aleatoria >= observada) = {p:.4f}")
    z = (observada - nulo.mean()) / nulo.std()
    print(f"  z = {z:+.2f}")

    print("\n" + "-" * 72)
    print(f"VEREDICTO (b): {'PASA' if p < UMBRAL_P else 'NO PASA'} el umbral "
          f"p<{UMBRAL_P} fijado de antemano")
    print("-" * 72)

    # ------------------------------------------------------- sensibilidad ---
    # Reported whatever they say. The ZONA CENTRO concern was raised BEFORE the
    # pre-registered test was run -- it is a stated caveat, not a rescue
    # attempt -- and the AGEB-level variant is included precisely because it is
    # the one configuration that "passes", so the reason it does not count is
    # on the record rather than left out.
    print("\n=== SENSIBILIDAD (el veredicto lo fija la prueba pre-registrada) ===")

    def corre(mat: np.ndarray, idx: list[int], etiqueta: str) -> None:
        obs, k = cohesion(mat[idx]), len(idx)
        nulo = np.array([cohesion(mat[rng.choice(len(mat), k, replace=False)])
                         for _ in range(N_PERMUTACIONES)])
        pv = float((nulo >= obs).mean())
        print(f"  {etiqueta:<44} k={k:<3} obs={obs:.4f}  nulo={nulo.mean():.4f}"
              f"±{nulo.std():.4f}  z={(obs - nulo.mean()) / nulo.std():+.2f}  "
              f"p={pv:.4f}  {'pasa' if pv < UMBRAL_P else 'no pasa'}")

    sin_centro = [i for i in positivas if nombres[i] != "ZONA CENTRO"]
    corre(perfiles, positivas, "pre-registrada: colonias")
    corre(perfiles, sin_centro, "colonias sin ZONA CENTRO")

    publicadas = [n for n in (INUNDADAS[c] for c in INUNDADAS) if n]
    idx_ageb = list(np.where(np.isin(colonia, publicadas))[0])
    corre(tabla, idx_ageb, "a nivel AGEB (prohibido por §3.6)")
    idx_ageb_sc = list(np.where(np.isin(
        colonia, [n for n in publicadas if n != "ZONA CENTRO"]))[0])
    corre(tabla, idx_ageb_sc, "a nivel AGEB, sin ZONA CENTRO")

    print("\n  Nota: la variante a nivel AGEB es la unica que pasa, y lo hace")
    print("  porque 21 de sus 29 filas son ZONA CENTRO -- una colonia, una")
    print("  etiqueta, y la de mayor cohesion interna del conjunto. Inflar n con")
    print("  unidades no independientes es el fallo que §3.6 prohibio por escrito.")

    # ------------------------------------------------------------ potencia --
    print("\n=== POTENCIA: que cohesion habria hecho falta ===")
    for k in (len(positivas), 16):
        nulo = np.array([cohesion(perfiles[rng.choice(len(perfiles), k, replace=False)])
                         for _ in range(N_PERMUTACIONES)])
        print(f"  con k={k:<3} p<{UMBRAL_P} exige cohesion >= "
              f"{np.quantile(nulo, 1 - UMBRAL_P):.4f}   (observada {observada:.4f})")
    print("  Con las 16 completas seguiria sin pasar: el efecto es chico, no")
    print("  solamente mal medido. Las etiquetas faltantes no eran la restriccion.")


if __name__ == "__main__":
    main()
