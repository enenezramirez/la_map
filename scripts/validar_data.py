"""
Validate the files published in data/ against the invariants the site relies on.

Standard library only, so it runs without the pipeline's environment and
without raw_data/:

    python3 scripts/validar_data.py

Prints one line per check and exits 1 if any of them fails.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
from pathlib import Path

# Adding a municipality changes these on purpose: update them in the same change.
MUNICIPIOS = {"Saltillo": 342, "Ramos Arizpe": 61, "Arteaga": 28}
MUNICIPIO_CON_ATLAS = "Saltillo"

LIMITE_CAPAS_BYTES = 5 * 1024 * 1024
FUERA_DEL_LIMITE = {"calles.json"}

# West, south, east, north. Generous on purpose: it catches swapped axes and
# a wrong CRS, not a boundary that moved.
REGION = (-101.2, 25.1, -100.4, 25.8)

TOLERANCIA = 1e-6

CAMPOS_SERVICIOS = {
    "CVEGEO", "NOM_MUN", "COLONIA", "POBTOT", "TVIVHAB", "PCT_ELECTRICIDAD",
    "PCT_AGUA", "PCT_DRENAJE", "PCT_INTERNET", "SERVICIOS_INDEX", "MOTIVO_SIN_DATO",
}
CAMPOS_INVERSION = {
    "CVEGEO", "NOM_MUN", "COLONIA", "SERVICIOS_INDEX", "SCORE_ESCUELA",
    "SCORE_SALUD", "SCORE_SUPERMERCADO", "COMERCIOS_INDEX", "RIESGO_INDEX",
    "RIESGO_EVALUADO", "INVERSION_INDEX", "MOTIVO_SIN_DATO",
}
CAMPOS_RIESGO = {"INTENSIDAD", "PUNTAJE", "TITULO", "FENOMENO", "FUENTE", "FECHA"}
CAMPOS_CAUCES = {"ORDEN", "CONDICION", "ANIO_CAPTURA", "FUENTE", "FECHA"}
CAMPOS_COMPARTIDOS = ("NOM_MUN", "COLONIA", "SERVICIOS_INDEX", "MOTIVO_SIN_DATO")
PUNTAJES = ("SCORE_ESCUELA", "SCORE_SALUD", "SCORE_SUPERMERCADO")

# Layer file -> the pipeline constant that lists its published levels.
CAPAS_RIESGO = {
    "riesgo_inundacion.geojson": "NIVELES_ELEVADOS",
    "riesgo_deslizamientos.geojson": "NIVELES_ELEVADOS",
    "riesgo_quimico.geojson": "NIVELES_ELEVADOS_QUIMICO",
}

VIAS_CATASTRO = {"exacto", "palabras", "espacios"}
CAMPOS_CATASTRO = {"clase", "valor", "via"}
CAMPOS_CATASTRO_OPCIONALES = {"nombre_catastro"}

# Properties app.js attaches to a feature at run time; no file carries them.
AGREGADOS_EN_NAVEGADOR = {"CATASTRO"}

CONSTANTES_PIPELINE = (
    "PESO_SERVICIOS", "PESO_COMERCIOS", "PESO_RIESGO", "RADIO_MAX_KM",
    "FORMATO_INDICE_CALLES", "DECIMALES_COORDENADA", "CAUCES_ORDEN_MINIMO",
    "NIVELES_ELEVADOS", "NIVELES_ELEVADOS_QUIMICO",
)

# State, municipality, locality and AGEB. INEGI's AGEB check character is a
# digit or "A".
CLAVE_AGEB = re.compile(r"\d{12}[0-9A]")
TEXTO_PELIGROSO = re.compile(r"[<>\x00-\x1f\x7f]")
PROPIEDAD_LEIDA = re.compile(
    r"\b(?:props|properties)\.([A-Z][A-Z0-9_]+)\b|campoValor:\s*'([A-Z][A-Z0-9_]+)'"
)


class Informe:
    def __init__(self) -> None:
        self.fallos = 0

    def revisar(self, nombre: str, malos=()) -> None:
        """Record one check. `malos` lists what broke it; empty means it holds."""
        malos = list(malos)
        if not malos:
            print(f"ok    {nombre}")
            return
        self.fallos += 1
        ejemplos = ", ".join(str(m) for m in malos[:3])
        print(f"FAIL  {nombre}: {len(malos)} (e.g. {ejemplos})")


def es_numero(valor) -> bool:
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def es_porcentaje(valor) -> bool:
    return es_numero(valor) and 0 <= valor <= 100


def es_texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def leer_constantes_pipeline(ruta: Path) -> dict:
    """Read literal module-level constants without importing the pipeline."""
    constantes = {}
    for nodo in ast.parse(ruta.read_text(encoding="utf-8")).body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            destino = nodo.targets[0]
            if isinstance(destino, ast.Name) and destino.id in CONSTANTES_PIPELINE:
                constantes[destino.id] = ast.literal_eval(nodo.value)
    return constantes


def leer_constante_js(fuente: str, nombre: str):
    hallado = re.search(rf"^const {nombre}\s*=\s*([0-9.]+);", fuente, re.MULTILINE)
    return float(hallado.group(1)) if hallado else None


def propiedades(geojson: dict) -> list:
    return [f["properties"] for f in geojson["features"]]


def cadenas(objeto):
    if isinstance(objeto, str):
        yield objeto
    elif isinstance(objeto, dict):
        for clave, valor in objeto.items():
            yield clave
            yield from cadenas(valor)
    elif isinstance(objeto, list):
        for valor in objeto:
            yield from cadenas(valor)


def vertices(coordenadas):
    if coordenadas and isinstance(coordenadas[0], list):
        for parte in coordenadas:
            yield from vertices(parte)
    else:
        yield coordenadas


def validar_agebs(inf: Informe, servicios: list, inversion: list, c: dict) -> dict:
    """Check both AGEB layers and return the investment properties by CVEGEO."""
    for nombre, capa, campos in (
        ("services", servicios, CAMPOS_SERVICIOS),
        ("investment", inversion, CAMPOS_INVERSION),
    ):
        conteo: dict = {}
        for p in capa:
            conteo[p.get("NOM_MUN")] = conteo.get(p.get("NOM_MUN"), 0) + 1
        inf.revisar(
            f"{nombre}: {sum(MUNICIPIOS.values())} sectors, split by municipality as declared",
            [] if conteo == MUNICIPIOS else [conteo],
        )
        inf.revisar(
            f"{nombre}: every sector carries exactly the declared fields",
            [p.get("CVEGEO") for p in capa if set(p) != campos],
        )
        claves = [p.get("CVEGEO") for p in capa]
        inf.revisar(
            f"{nombre}: CVEGEO has INEGI's 13-character form and is unique",
            [k for k in claves if not (isinstance(k, str) and CLAVE_AGEB.fullmatch(k))]
            + sorted({k for k in claves if claves.count(k) > 1}),
        )
        inf.revisar(
            f"{nombre}: COLONIA is never empty",
            [p.get("CVEGEO") for p in capa if not es_texto(p.get("COLONIA"))],
        )

    por_clave_srv = {p["CVEGEO"]: p for p in servicios}
    por_clave = {p["CVEGEO"]: p for p in inversion}
    inf.revisar(
        "both AGEB layers hold the same sectors",
        sorted(set(por_clave_srv) ^ set(por_clave)),
    )
    inf.revisar(
        "fields present in both AGEB layers agree",
        [
            f"{k}.{campo}"
            for k in set(por_clave_srv) & set(por_clave)
            for campo in CAMPOS_COMPARTIDOS
            if por_clave_srv[k].get(campo) != por_clave[k].get(campo)
        ],
    )

    porcentajes = ("PCT_ELECTRICIDAD", "PCT_AGUA", "PCT_DRENAJE", "PCT_INTERNET", "SERVICIOS_INDEX")
    inf.revisar(
        "services: percentages are null or within 0-100",
        [
            f"{p['CVEGEO']}.{campo}"
            for p in servicios
            for campo in porcentajes
            if p.get(campo) is not None and not es_porcentaje(p.get(campo))
        ],
    )
    inf.revisar(
        "services: population and dwellings are null or non-negative",
        [
            f"{p['CVEGEO']}.{campo}"
            for p in servicios
            for campo in ("POBTOT", "TVIVHAB")
            if p.get(campo) is not None and not (es_numero(p.get(campo)) and p[campo] >= 0)
        ],
    )
    inf.revisar(
        "services: a sector has no index exactly when it states why (MOTIVO_SIN_DATO)",
        [
            p["CVEGEO"]
            for p in servicios
            if (p.get("SERVICIOS_INDEX") is None) != es_texto(p.get("MOTIVO_SIN_DATO"))
        ],
    )

    inf.revisar(
        "investment: proximity scores and COMERCIOS_INDEX are within 0-100",
        [
            f"{p['CVEGEO']}.{campo}"
            for p in inversion
            for campo in PUNTAJES + ("COMERCIOS_INDEX",)
            if not es_porcentaje(p.get(campo))
        ],
    )
    inf.revisar(
        "investment: COMERCIOS_INDEX is the mean of the three proximity scores",
        [
            p["CVEGEO"]
            for p in inversion
            if all(es_numero(p.get(s)) for s in PUNTAJES + ("COMERCIOS_INDEX",))
            and abs(sum(p[s] for s in PUNTAJES) / 3 - p["COMERCIOS_INDEX"]) > TOLERANCIA
        ],
    )
    inf.revisar(
        "investment: RIESGO_EVALUADO is a boolean",
        [p["CVEGEO"] for p in inversion if not isinstance(p.get("RIESGO_EVALUADO"), bool)],
    )
    inf.revisar(
        "investment: RIESGO_INDEX is a 0-100 figure when assessed and null when not",
        [
            p["CVEGEO"]
            for p in inversion
            if (p.get("RIESGO_EVALUADO") is True) != es_porcentaje(p.get("RIESGO_INDEX"))
            or (p.get("RIESGO_EVALUADO") is not True and p.get("RIESGO_INDEX") is not None)
        ],
    )
    inf.revisar(
        f"investment: no sector outside {MUNICIPIO_CON_ATLAS} is marked as assessed",
        [
            p["CVEGEO"]
            for p in inversion
            if p.get("NOM_MUN") != MUNICIPIO_CON_ATLAS and p.get("RIESGO_EVALUADO") is not False
        ],
    )

    def indice_esperado(p):
        if p.get("SERVICIOS_INDEX") is None or p.get("RIESGO_EVALUADO") is not True:
            return None
        peso_base = c["PESO_SERVICIOS"] + c["PESO_COMERCIOS"]
        base = (
            p["SERVICIOS_INDEX"] * c["PESO_SERVICIOS"]
            + p["COMERCIOS_INDEX"] * c["PESO_COMERCIOS"]
        ) / peso_base
        return min(100.0, max(0.0, base - p["RIESGO_INDEX"] * c["PESO_RIESGO"]))

    sin_indice, distintos = [], []
    for p in inversion:
        try:
            esperado = indice_esperado(p)
        except (TypeError, KeyError):
            continue
        publicado = p.get("INVERSION_INDEX")
        if (esperado is None) != (publicado is None):
            sin_indice.append(p["CVEGEO"])
        elif esperado is not None and (
            not es_numero(publicado) or abs(esperado - publicado) > TOLERANCIA
        ):
            distintos.append(p["CVEGEO"])
    inf.revisar(
        "investment: the index is null exactly when services or the flood assessment are missing",
        sin_indice,
    )
    inf.revisar(
        "investment: the published index matches its formula and components",
        distintos,
    )
    return por_clave


def validar_riesgo(inf: Informe, archivo: str, capa: list, niveles: list) -> None:
    inf.revisar(
        f"{archivo}: every zone carries exactly the declared fields",
        [i for i, p in enumerate(capa) if set(p) != CAMPOS_RIESGO],
    )
    inf.revisar(
        f"{archivo}: INTENSIDAD is one of the published levels {niveles}",
        sorted({str(p.get("INTENSIDAD")) for p in capa if p.get("INTENSIDAD") not in niveles}),
    )
    inf.revisar(
        f"{archivo}: source, date, title and phenomenon are stated on every zone",
        [
            i
            for i, p in enumerate(capa)
            if not all(es_texto(p.get(campo)) for campo in ("FUENTE", "FECHA", "TITULO", "FENOMENO"))
        ],
    )
    inf.revisar(f"{archivo}: the layer is not empty", [] if capa else ["0 zones"])


def validar_cauces(inf: Informe, capa: list, orden_minimo: int) -> None:
    inf.revisar(
        "streams: every course carries exactly the declared fields",
        [i for i, p in enumerate(capa) if set(p) != CAMPOS_CAUCES],
    )
    inf.revisar(
        f"streams: ORDEN is an integer of at least {orden_minimo}",
        [
            i
            for i, p in enumerate(capa)
            if not (type(p.get("ORDEN")) is int and p["ORDEN"] >= orden_minimo)
        ],
    )
    inf.revisar(
        "streams: ANIO_CAPTURA is an integer year",
        [
            i
            for i, p in enumerate(capa)
            if not (type(p.get("ANIO_CAPTURA")) is int and 1900 <= p["ANIO_CAPTURA"] <= 2100)
        ],
    )
    inf.revisar(
        "streams: source, date and condition are stated on every course",
        [
            i
            for i, p in enumerate(capa)
            if not all(es_texto(p.get(campo)) for campo in ("FUENTE", "FECHA", "CONDICION"))
        ],
    )


def validar_catastro(inf: Informe, catastro: dict, por_clave: dict) -> None:
    inf.revisar(
        "cadastre: the file states its source, edition and the tax-base note",
        [campo for campo in ("fuente", "edicion", "nota") if not es_texto(str(catastro.get(campo) or ""))],
    )
    sectores = catastro.get("sectores")
    if not isinstance(sectores, dict):
        inf.revisar("cadastre: `sectores` is an object keyed by CVEGEO", [type(sectores).__name__])
        return
    inf.revisar(
        f"cadastre: every key is a published sector of {MUNICIPIO_CON_ATLAS}",
        [
            k
            for k in sectores
            if k not in por_clave or por_clave[k].get("NOM_MUN") != MUNICIPIO_CON_ATLAS
        ],
    )
    inf.revisar(
        "cadastre: every record has the declared fields",
        [
            k
            for k, d in sectores.items()
            if not isinstance(d, dict)
            or not CAMPOS_CATASTRO <= set(d) <= CAMPOS_CATASTRO | CAMPOS_CATASTRO_OPCIONALES
        ],
    )
    registros = {k: d for k, d in sectores.items() if isinstance(d, dict)}
    inf.revisar(
        "cadastre: valor is null or a positive figure",
        [
            k
            for k, d in registros.items()
            if d.get("valor") is not None and not (es_numero(d.get("valor")) and d["valor"] > 0)
        ],
    )
    inf.revisar(
        "cadastre: clase is stated and via is a known matching rule",
        [
            k
            for k, d in registros.items()
            if not es_texto(d.get("clase")) or d.get("via") not in VIAS_CATASTRO
        ],
    )


def validar_calles(inf: Informe, calles: dict, por_clave: dict, c: dict, formato_js) -> None:
    inf.revisar(
        "streets: `formato` matches FORMATO_INDICE_CALLES in the pipeline and in app.js",
        []
        if calles.get("formato") == c["FORMATO_INDICE_CALLES"] == formato_js
        else [(calles.get("formato"), c["FORMATO_INDICE_CALLES"], formato_js)],
    )
    catalogos = ("tipos", "asentamientos", "municipios", "cps", "agebs")
    inf.revisar(
        "streets: every catalog is a list of text",
        [
            nombre
            for nombre in catalogos
            if not isinstance(calles.get(nombre), list)
            or not all(es_texto(v) for v in calles[nombre])
        ],
    )
    if not all(isinstance(calles.get(nombre), list) for nombre in catalogos + ("calles",)):
        return
    inf.revisar(
        "streets: every AGEB in the index is a published sector",
        [k for k in calles["agebs"] if k not in por_clave],
    )

    tamanos = {nombre: len(calles[nombre]) for nombre in catalogos}

    def indices_validos(valores, catalogo) -> bool:
        return (
            isinstance(valores, list)
            and bool(valores)
            and all(type(i) is int and 0 <= i < tamanos[catalogo] for i in valores)
        )

    def zona_valida(zona) -> bool:
        if not (isinstance(zona, list) and len(zona) == 5):
            return False
        tipo, asentamientos, municipio, cps, agebs = zona
        return (
            indices_validos([tipo], "tipos")
            and indices_validos(asentamientos, "asentamientos")
            and indices_validos([municipio], "municipios")
            and isinstance(cps, list)
            and all(type(i) is int and 0 <= i < tamanos["cps"] for i in cps)
            and indices_validos(agebs, "agebs")
        )

    inf.revisar(
        "streets: every street has a name and zones that resolve in the catalogs",
        [
            calle[0] if isinstance(calle, list) and calle else i
            for i, calle in enumerate(calles["calles"])
            if not (
                isinstance(calle, list)
                and len(calle) == 2
                and es_texto(calle[0])
                and isinstance(calle[1], list)
                and calle[1]
                and all(zona_valida(z) for z in calle[1])
            )
        ],
    )


def validar_geometria(inf: Informe, archivo: str, ruta: Path, decimales: int) -> None:
    geojson = json.loads(ruta.read_text(encoding="utf-8"), parse_float=str)
    crs = (geojson.get("crs") or {}).get("properties", {}).get("name")
    inf.revisar(
        f"{archivo}: coordinates are declared as CRS84 (longitude, latitude)",
        [] if crs == "urn:ogc:def:crs:OGC:1.3:CRS84" else [crs],
    )
    oeste, sur, este, norte = REGION
    fuera, largos = [], []
    for i, feature in enumerate(geojson["features"]):
        for lon, lat in (v[:2] for v in vertices(feature["geometry"]["coordinates"])):
            if not (oeste <= float(lon) <= este and sur <= float(lat) <= norte):
                fuera.append(i)
            if any(len(str(v).partition(".")[2]) > decimales for v in (lon, lat)):
                largos.append(i)
    inf.revisar(f"{archivo}: every vertex falls inside the metropolitan region", sorted(set(fuera)))
    inf.revisar(
        f"{archivo}: no coordinate carries more than {decimales} decimals (exportar_geojson)",
        sorted(set(largos)),
    )


def validar_contrato(inf: Informe, app_js: str, c: dict) -> None:
    radio_js = leer_constante_js(app_js, "RADIO_CERCANIA_KM")
    inf.revisar(
        "contract: RADIO_MAX_KM (pipeline) equals RADIO_CERCANIA_KM (app.js)",
        [] if radio_js == c["RADIO_MAX_KM"] else [(c["RADIO_MAX_KM"], radio_js)],
    )
    publicados = CAMPOS_SERVICIOS | CAMPOS_INVERSION | CAMPOS_RIESGO | CAMPOS_CAUCES
    leidos = {a or b for a, b in PROPIEDAD_LEIDA.findall(app_js)}
    inf.revisar(
        "contract: every property app.js reads is one a published layer carries",
        sorted(leidos - publicados - AGREGADOS_EN_NAVEGADOR),
    )


def validar_peso(inf: Informe, data: Path) -> None:
    total = sum(
        ruta.stat().st_size
        for ruta in data.iterdir()
        if ruta.is_file() and ruta.name not in FUERA_DEL_LIMITE
    )
    inf.revisar(
        f"size: the layers weigh {total / 1048576:.2f} MB, within the 5 MB budget",
        [] if total <= LIMITE_CAPAS_BYTES else [f"{total} bytes"],
    )


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    analizador.add_argument(
        "--raiz",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (default: the one this script lives in)",
    )
    raiz = analizador.parse_args().raiz
    data = raiz / "data"
    inf = Informe()

    constantes = leer_constantes_pipeline(raiz / "scripts" / "process_data.py")
    faltantes = [n for n in CONSTANTES_PIPELINE if n not in constantes]
    inf.revisar("pipeline: every constant this script depends on is still declared", faltantes)
    if faltantes:
        return 1
    app_js = (raiz / "app.js").read_text(encoding="utf-8")

    geojson = [
        "servicios_basicos.geojson", "indice_inversion.geojson", "cauces_inegi.geojson",
        *CAPAS_RIESGO,
    ]
    archivos = geojson + ["valor_catastral.json", "calles.json"]
    # A file nobody listed here has no entry in DATOS.md §1.1 saying it may be published.
    inf.revisar(
        "data/ holds only the files listed here",
        sorted(r.name for r in data.iterdir() if r.is_file() and r.name not in archivos),
    )
    contenido, ilegibles = {}, []
    for archivo in archivos:
        try:
            contenido[archivo] = json.loads((data / archivo).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            ilegibles.append(f"{archivo}: {error}")
    inf.revisar("every published file exists and parses as JSON", ilegibles)
    if ilegibles:
        return 1

    por_clave = validar_agebs(
        inf,
        propiedades(contenido["servicios_basicos.geojson"]),
        propiedades(contenido["indice_inversion.geojson"]),
        constantes,
    )
    for archivo, constante in CAPAS_RIESGO.items():
        validar_riesgo(inf, archivo, propiedades(contenido[archivo]), constantes[constante])
    validar_cauces(
        inf, propiedades(contenido["cauces_inegi.geojson"]), constantes["CAUCES_ORDEN_MINIMO"]
    )
    validar_catastro(inf, contenido["valor_catastral.json"], por_clave)
    validar_calles(
        inf,
        contenido["calles.json"],
        por_clave,
        constantes,
        leer_constante_js(app_js, "FORMATO_INDICE_CALLES"),
    )
    for archivo in geojson:
        validar_geometria(inf, archivo, data / archivo, constantes["DECIMALES_COORDENADA"])
    for archivo in archivos:
        inf.revisar(
            f"{archivo}: no text carries markup or control characters",
            sorted({t for t in cadenas(contenido[archivo]) if TEXTO_PELIGROSO.search(t)}),
        )
    validar_contrato(inf, app_js, constantes)
    validar_peso(inf, data)

    if inf.fallos:
        print(f"\n{inf.fallos} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
