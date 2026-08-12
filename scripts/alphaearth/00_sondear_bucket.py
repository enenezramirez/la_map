"""Probe the anonymous AEF mirror to learn its layout without adding pyarrow.

DATOS.md 3.6 approved reading the STAC geoparquet index to find the zone-14N
tiles covering the project bbox. That index needs pyarrow, a second new
dependency where the entry promised one. So first check whether the bucket's
own object listing names tiles in a way that makes the index unnecessary.

Note on the URI in 3.6: s3://us-west-2.opendata.source.coop/... names a BUCKET
called "us-west-2.opendata.source.coop", not a hostname. The HTTPS form is
path-style against the regional S3 endpoint.
"""

import urllib.request
# nosec B405 - same justification as the ET.fromstring call below.
import xml.etree.ElementTree as ET  # nosec B405

BUCKET = "us-west-2.opendata.source.coop"
ENDPOINTS = [
    f"https://s3.us-west-2.amazonaws.com/{BUCKET}/",
    f"https://{BUCKET}.s3.us-west-2.amazonaws.com/",
]


def listar(url: str, prefix: str, delimiter: str = "/", max_keys: int = 30):
    """Print an S3 ListObjectsV2 response: common prefixes and keys."""
    full = f"{url}?list-type=2&prefix={prefix}&delimiter={delimiter}&max-keys={max_keys}"
    print(f"\n--- {full}")
    try:
        with urllib.request.urlopen(full, timeout=30) as r:  # nosec B310 - fixed https host
            cuerpo = r.read()
    except Exception as e:  # noqa: BLE001 - probing, any failure is informative
        print(f"    FALLO: {type(e).__name__}: {e}")
        return None

    try:
        # nosec B314 - AWS S3's own ListObjectsV2 XML, over TLS from a
        # hard-coded host. stdlib ElementTree resolves no external entities, so
        # XXE does not apply; the residual entity-expansion DoS would take down
        # a local one-off script. Not worth adding defusedxml.
        raiz = ET.fromstring(cuerpo)  # nosec B314
    except ET.ParseError:
        print(f"    no es XML: {cuerpo[:200]!r}")
        return None

    prefijos, claves, tam = [], [], {}
    for e in raiz.iter():
        if e.tag.endswith("}Prefix") and e.text and e.text != prefix:
            prefijos.append(e.text)
    for c in raiz.iter():
        if c.tag.endswith("}Contents"):
            k = s = None
            for h in c:
                if h.tag.endswith("}Key"):
                    k = h.text
                if h.tag.endswith("}Size"):
                    s = int(h.text or 0)
            if k:
                claves.append(k)
                tam[k] = s
    print(f"    prefijos ({len(prefijos)}): {prefijos[:25]}")
    for k in claves[:12]:
        print(f"    clave: {k}  ({tam[k]:,} B)")
    return prefijos, claves, tam


base = None
for cand in ENDPOINTS:
    r = listar(cand, "tge-labs/aef/", max_keys=10)
    if r is not None:
        base = cand
        break

if base:
    print(f"\n=== endpoint que sirve: {base}")
    for p in ["tge-labs/aef/v1/", "tge-labs/aef/v1/annual/"]:
        listar(base, p, max_keys=30)
