"""Re-derive the figures in DATOS.md 3.3 from CONAFOR's WFS extracts.

Archived one-off analysis, not pipeline: nothing here feeds published data.
DATOS.md 3.3 has the queries that produce the extracts.

    python scripts/conafor/medir_capas.py --agebs data/servicios_basicos.geojson \
        --indice data/indice_inversion.geojson \
        --prioridad prioridad.json --incendios inc_2021.json inc_2022.json ...
"""

import argparse
import json
import re
from collections import Counter
from operator import itemgetter

import shapely
from pyproj import Transformer
from shapely.geometry import LineString, shape
from shapely.ops import transform, unary_union

A_METRICO = Transformer.from_crs(4326, 6372, always_xy=True).transform
MUNICIPIOS = {"004": "Arteaga", "027": "Ramos Arizpe", "030": "Saltillo"}
CLASES = ("No aplica", "Muy bajo", "Bajo", "Moderado", "Alto", "Muy alto")
CLASES_ALTAS = ("Alto", "Muy alto")
PUNTAJE_CLASE = {"Bajo": 25, "Moderado": 50, "Alto": 75, "Muy alto": 100}
CAJA_INCENDIOS = (-101.2, -100.3, 25.15, 25.7)
CERCA_M = 500
CLAVE_COAHUILA = "05"


def leer_entidades(ruta):
    """Yield every complete feature, because the 2026-11-07 extract hit a size cap."""
    with open(ruta, encoding="utf-8") as archivo:
        texto = archivo.read()
    i = re.search(r'"features"\s*:\s*\[', texto).end()
    decodificador = json.JSONDecoder()
    while True:
        while i < len(texto) and (texto[i] == "," or texto[i].isspace()):
            i += 1
        try:
            entidad, i = decodificador.raw_decode(texto, i)
        except json.JSONDecodeError:
            return
        yield entidad


def geometria_metrica(entidad):
    g = transform(A_METRICO, shape(entidad["geometry"]))
    return g if g.is_valid else g.buffer(0)


def municipio_de(ageb):
    return ageb["propiedades"]["CVEGEO"][2:5]


def cargar_agebs(ruta):
    return [
        {"propiedades": e["properties"], "geometria": geometria_metrica(e)}
        for e in leer_entidades(ruta)
    ]


def medir_reticula(geometria):
    xy = shapely.get_coordinates(geometria)
    for eje, nombre in enumerate("xy"):
        _, repetidos = Counter(int(v % 30) for v in xy[:, eje]).most_common(1)[0]
        print(f"  {nombre}: {repetidos / len(xy):.1%} of vertices share one residue mod 30 m")


def medir_clases(clases, agebs):
    for cve, nombre in MUNICIPIOS.items():
        disponibles = {c: g for (m, c), (g, _) in clases.items() if m == cve}
        area_total = sum(a["geometria"].area for a in agebs if municipio_de(a) == cve)
        partes = []
        for clase in CLASES:
            if clase not in disponibles:
                partes.append(f"{clase}=not fetched")
                continue
            traslape = sum(
                a["geometria"].intersection(disponibles[clase]).area
                for a in agebs
                if municipio_de(a) == cve
            )
            partes.append(f"{clase}={traslape / area_total:.3%}")
        print(f"  {nombre}: " + ", ".join(partes))


def medir_cuadre(clases):
    for cve, nombre in MUNICIPIOS.items():
        if any((cve, c) not in clases for c in CLASES):
            print(f"  {nombre}: classes missing")
            continue
        atributos = clases[(cve, CLASES[0])][1]
        total = sum(clases[(cve, c)][0].area for c in CLASES) / 1e4
        altas = sum(clases[(cve, c)][0].area for c in CLASES_ALTAS) / 1e4
        print(f"  {nombre}: all classes {total:,.1f} ha vs Sup_mun {atributos['Sup_mun']:,.1f}")
        print(f"  {nombre}: Alto + Muy alto {altas:,.1f} ha vs Sup_eleg {atributos['Sup_eleg']:,.1f}")


def medir_penalizacion(clases, agebs):
    """Score each AGEB the way RIESGO_INDEX does, with Moderado standing in for Medio."""
    for cve, nombre in MUNICIPIOS.items():
        if any((cve, c) not in clases for c in PUNTAJE_CLASE):
            print(f"Penalty in {nombre}: classes missing")
            continue
        filas = []
        for ageb in agebs:
            if municipio_de(ageb) != cve:
                continue
            g = ageb["geometria"]
            partes = {c: g.intersection(clases[(cve, c)][0]).area / g.area for c in PUNTAJE_CLASE}
            filas.append((sum(partes[c] * p for c, p in PUNTAJE_CLASE.items()), partes, ageb))
        filas.sort(key=itemgetter(0), reverse=True)

        print(f"Penalty in {nombre}, {len(filas)} AGEBs:")
        for umbral in (0, 1, 5, 10, 25):
            print(f"  above {umbral}: {sum(1 for f in filas if f[0] > umbral)}")
        for clase in PUNTAJE_CLASE:
            partes = [f[1][clase] for f in filas]
            print(
                f"  {clase}: touches {sum(1 for v in partes if v > 0)}, "
                f"at least 1% in {sum(1 for v in partes if v >= 0.01)}, "
                f"at least 10% in {sum(1 for v in partes if v >= 0.1)}, "
                f"largest share {max(partes):.2%}"
            )
        for penalizacion, _, ageb in filas[:6]:
            p = ageb["propiedades"]
            print(f"  {p['CVEGEO']} {p['COLONIA']}: {penalizacion:.1f}, POBTOT={p['POBTOT']}")


def medir_cercania(altas, agebs):
    filas = []
    for ageb in agebs:
        g = ageb["geometria"]
        filas.append((g.distance(altas), g.intersection(altas).area / g.area, ageb))

    print("AGEBs touching Alto or Muy alto:")
    for _, parte, ageb in sorted((f for f in filas if f[1] > 0), key=lambda f: f[1]):
        p = ageb["propiedades"]
        print(f"  {p['CVEGEO']} {p['NOM_MUN']}: {parte:.2%}, POBTOT={p['POBTOT']}")

    cerca = [f[2] for f in filas if f[0] < CERCA_M]
    por_municipio = Counter(MUNICIPIOS[municipio_de(a)] for a in cerca)
    poblaciones = [a["propiedades"]["POBTOT"] for a in cerca]
    con_dato = [v for v in poblaciones if v is not None]
    print(f"AGEBs within {CERCA_M} m: {len(cerca)} {dict(por_municipio)}")
    print(f"  {len(con_dato)} with Census data: {sum(con_dato):,.0f} residents")
    print(f"  {len(poblaciones) - len(con_dato)} with null POBTOT")

    print("Distance from Arteaga AGEBs to Alto or Muy alto:")
    arteaga = sorted((f for f in filas if municipio_de(f[2]) == "004"), key=lambda f: f[0])
    for distancia, _, ageb in arteaga[:2]:
        p = ageb["propiedades"]
        print(f"  {p['CVEGEO']} {p['COLONIA']}: {distancia:,.0f} m")
    for distancia, _, ageb in arteaga:
        p = ageb["propiedades"]
        if p["CVEGEO"].startswith("050040107"):
            print(f"  {p['CVEGEO']} San Antonio de las Alazanas: {distancia:,.0f} m")


def medir_indice_inundacion(ruta):
    valores = [
        e["properties"]["RIESGO_INDEX"]
        for e in leer_entidades(ruta)
        if e["properties"]["CVEGEO"][2:5] == "030" and e["properties"]["RIESGO_INDEX"] is not None
    ]
    print(f"Flood RIESGO_INDEX in Saltillo, {len(valores)} AGEBs:")
    print(f"  above 1: {sum(1 for v in valores if v > 1)}")


def medir_prioridad(rutas, agebs):
    clases = {}
    for ruta in rutas:
        for entidad in leer_entidades(ruta):
            p = entidad["properties"]
            clave = (p["CVE_MUN"], p["Prioridad"])
            if clave not in clases:
                clases[clave] = (geometria_metrica(entidad), p)

    print("Vertices of Arteaga's Muy alto class, in EPSG:6372:")
    medir_reticula(clases[("004", "Muy alto")][0])
    print("Classes against the layer's own attributes:")
    medir_cuadre(clases)
    print("Share of each municipality's AGEB area, by class:")
    medir_clases(clases, agebs)
    medir_cercania(
        unary_union([g for (_, c), (g, _) in clases.items() if c in CLASES_ALTAS]), agebs
    )
    medir_penalizacion(clases, agebs)


def medir_margen_caja(huella):
    oeste, este, sur, norte = CAJA_INCENDIOS
    lados = {
        "north": ((oeste, norte), (este, norte)),
        "south": ((oeste, sur), (este, sur)),
        "west": ((oeste, sur), (oeste, norte)),
        "east": ((este, sur), (este, norte)),
    }
    print("Margin between the search box and the AGEB footprint:")
    for nombre, ((x0, y0), (x1, y1)) in lados.items():
        lado = LineString(
            [(x0 + (x1 - x0) * t / 200, y0 + (y1 - y0) * t / 200) for t in range(201)]
        )
        print(f"  {nombre}: {huella.distance(transform(A_METRICO, lado)) / 1000:.1f} km")


def describir_incendio(fila, campo):
    return (
        f"{fila[campo]:,.0f} m, {fila['clave']}, {fila['municipio']}, {fila['fecha']}, "
        f"{fila['ha']:,.2f} ha, {fila['vegetacion']}"
    )


def medir_incendios(rutas, agebs):
    huella = unary_union([a["geometria"] for a in agebs])
    huella_arteaga = unary_union([a["geometria"] for a in agebs if municipio_de(a) == "004"])
    medir_margen_caja(huella)

    filas = []
    for ruta in rutas:
        for entidad in leer_entidades(ruta):
            p = entidad["properties"]
            g = geometria_metrica(entidad)
            filas.append(
                {
                    "clave": p["CLAVEINC"],
                    "municipio": p["MUNICIPIO"],
                    "fecha": str(p["FECHAINIC"])[:10],
                    "ha": p["AREA_HA"] or 0,
                    "vegetacion": str(p["TIPVEG"]),
                    "a_agebs": g.distance(huella),
                    "a_arteaga": g.distance(huella_arteaga),
                }
            )
    coahuila = [f for f in filas if f["clave"].split("-")[1] == CLAVE_COAHUILA]
    otras = [f for f in filas if f["clave"].split("-")[1] != CLAVE_COAHUILA]
    a_agebs = itemgetter("a_agebs")
    a_arteaga = itemgetter("a_arteaga")

    print(f"Fires in the box: {len(filas)}")
    print(f"  Coahuila: {len(coahuila)}, {sum(f['ha'] for f in coahuila):,.2f} ha")
    print(f"  by municipality: {dict(Counter(f['municipio'] for f in coahuila))}")
    print(f"  other states: {len(otras)}")
    print("  nearest of those: " + describir_incendio(min(otras, key=a_agebs), "a_agebs"))

    print('Nearest fires in forest vegetation (TIPVEG starts with "Bosque"):')
    bosque = [f for f in filas if f["vegetacion"].startswith("Bosque")]
    for fila in sorted(bosque, key=a_agebs)[:2]:
        print("  " + describir_incendio(fila, "a_agebs"))

    print("Nearest fires to an Arteaga AGEB, wherever they were recorded:")
    for fila in sorted(filas, key=a_arteaga)[:2]:
        print("  " + describir_incendio(fila, "a_arteaga"))
    print("Nearest to an Arteaga AGEB among fires recorded in Arteaga:")
    en_arteaga = [f for f in filas if f["municipio"] == "Arteaga"]
    print("  " + describir_incendio(min(en_arteaga, key=a_arteaga), "a_arteaga"))

    print(f"Fires touching an AGEB or within {CERCA_M} m of one:")
    for fila in sorted((f for f in filas if f["a_agebs"] < CERCA_M), key=a_agebs):
        print("  " + describir_incendio(fila, "a_agebs"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agebs", required=True)
    parser.add_argument("--indice", required=True)
    parser.add_argument("--prioridad", nargs="+", required=True)
    parser.add_argument("--incendios", nargs="+", required=True)
    args = parser.parse_args()

    agebs = cargar_agebs(args.agebs)
    medir_prioridad(args.prioridad, agebs)
    medir_indice_inundacion(args.indice)
    medir_incendios(args.incendios, agebs)


if __name__ == "__main__":
    main()
