"""Find the AlphaEarth zone-14N tiles covering the project's extent.

Step 1 of the screening approved in DATOS.md 3.6. That step said to read the
4.99 MB STAC geoparquet index, which needs pyarrow -- a second new dependency
where the entry budgeted one. This does it without the index: every tile ships
a 27 KB .vrt whose first ~1.2 KB already carries the SRS and the GeoTransform,
so a ranged GET over the 520 tiles of zone 14N costs ~624 KB and answers the
same question.

Using the .vrt rather than the .tiff is not a convenience. The mirror's README
warns the COGs are stored "bottom-up" (origin bottom-left, positive y
resolution); reading the .tiff directly hands back a vertically MIRRORED image,
which would silently assign every AGEB the embedding of the wrong place. The
VRT's negative y resolution is the corrected view, and this script asserts it.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

BUCKET = "https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/"
PREFIJO = "tge-labs/aef/v1/annual/{anio}/14N/"

# The published extent of the 431 AGEBs, as recorded in DATOS.md 3.6.
BBOX_WGS84 = (-101.067, 25.263, -100.571, 25.607)
EPSG_ZONA = 32614  # WGS 84 / UTM zone 14N


@dataclass(frozen=True)
class Tesela:
    """A single COG's footprint, read from its VRT header."""

    clave: str
    oeste: float
    sur: float
    este: float
    norte: float
    ancho: int
    alto: int

    def intersecta(self, oeste: float, sur: float, este: float, norte: float) -> bool:
        return not (self.este <= oeste or self.oeste >= este
                    or self.norte <= sur or self.sur >= norte)


def listar_vrts(anio: int) -> list[str]:
    """Every .vrt key under the year's 14N directory, following pagination."""
    prefijo = PREFIJO.format(anio=anio)
    claves: list[str] = []
    token = None
    while True:
        url = f"{BUCKET}?list-type=2&prefix={prefijo}&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token, safe="")
        with urllib.request.urlopen(url, timeout=60) as r:  # nosec B310 - fixed https host
            arbol = ET.fromstring(r.read())
        for contenido in arbol.iter():
            if contenido.tag.endswith("}Contents"):
                for hijo in contenido:
                    if hijo.tag.endswith("}Key") and (hijo.text or "").endswith(".vrt"):
                        claves.append(hijo.text or "")
        token = next((e.text for e in arbol.iter()
                      if e.tag.endswith("}NextContinuationToken")), None)
        if not token:
            return claves


def leer_cabecera(clave: str, bytes_cabecera: int = 1400) -> Tesela | None:
    """Range-GET a VRT's opening bytes and derive its UTM footprint."""
    peticion = urllib.request.Request(
        BUCKET + clave, headers={"Range": f"bytes=0-{bytes_cabecera}"}
    )
    with urllib.request.urlopen(peticion, timeout=60) as r:  # nosec B310 - fixed https host
        texto = r.read().decode("utf-8", "replace")

    dims = re.search(r'rasterXSize="(\d+)"\s+rasterYSize="(\d+)"', texto)
    gt = re.search(r"<GeoTransform>([^<]+)</GeoTransform>", texto)
    if not dims or not gt:
        return None
    if "32614" not in texto:
        raise ValueError(f"{clave}: no declara EPSG:32614")

    ancho, alto = int(dims.group(1)), int(dims.group(2))
    ox, px, _, oy, _, py = [float(v) for v in gt.group(1).split(",")]
    # The VRT is the corrected, north-up view. A positive y step would mean the
    # raw bottom-up array leaked through, and every footprint below would be
    # flipped -- so refuse rather than compute a plausible wrong answer.
    if py >= 0:
        raise ValueError(f"{clave}: y-res {py} >= 0, el VRT no corrigio el bottom-up")

    return Tesela(clave, ox, oy + alto * py, ox + ancho * px, oy, ancho, alto)


def main(anio: int = 2024) -> None:
    from pyproj import Transformer

    hacia_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG_ZONA}", always_xy=True)
    oeste, sur = hacia_utm.transform(BBOX_WGS84[0], BBOX_WGS84[1])
    este, norte = hacia_utm.transform(BBOX_WGS84[2], BBOX_WGS84[3])
    print(f"bbox del proyecto en EPSG:{EPSG_ZONA}:")
    print(f"  E {oeste:,.0f} .. {este:,.0f}   N {sur:,.0f} .. {norte:,.0f}")
    print(f"  ({(este - oeste) / 1000:.1f} x {(norte - sur) / 1000:.1f} km)")

    claves = listar_vrts(anio)
    print(f"\n{len(claves)} VRTs en {anio}/14N; leyendo cabeceras...")
    with ThreadPoolExecutor(max_workers=12) as pool:
        teselas = [t for t in pool.map(leer_cabecera, claves) if t]
    print(f"cabeceras leidas: {len(teselas)}  (~{len(teselas) * 1400 / 1024:.0f} KB)")

    tocan = [t for t in teselas if t.intersecta(oeste, sur, este, norte)]
    print(f"\n=== {len(tocan)} tesela(s) cubren la extension del proyecto ===")
    for t in sorted(tocan, key=lambda x: x.clave):
        ancho_km = (min(t.este, este) - max(t.oeste, oeste)) / 1000
        alto_km = (min(t.norte, norte) - max(t.sur, sur)) / 1000
        print(f"  {t.clave.split('/')[-1]}")
        print(f"    E {t.oeste:,.0f}..{t.este:,.0f}  N {t.sur:,.0f}..{t.norte:,.0f}"
              f"  ({t.ancho}x{t.alto})")
        print(f"    solape con el proyecto: {ancho_km:.1f} x {alto_km:.1f} km")


if __name__ == "__main__":
    main()
