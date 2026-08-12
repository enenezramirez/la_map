# AlphaEarth screening — one-off analysis, not part of the pipeline

These five scripts are the screening approved in `DATOS.md §3.6` and run on
2026-08-11. They are archived here so the numbers that entry publishes can be
re-derived rather than taken on trust — the same standard this project applies
to every external source.

**They are not part of the data pipeline.** `scripts/process_data.py` builds
everything in `data/` and does not import anything from this folder. Nothing
here produces a published layer, and by the rule in `§3.6` nothing it produces
may reach the Investment Index or share a field with a cited figure.

## Running them

Needs one dependency the pipeline does not use:

```bash
venv/Scripts/pip install rasterio
```

Run in order. Each writes its intermediate to `raw_data/alphaearth/`, which is
gitignored — these are working files, not published data.

| script | what it does | cost |
|---|---|---|
| `00_sondear_bucket.py` | learns the mirror's layout | a few KB |
| `01_localizar_teselas.py` | finds the zone-14N tiles covering the project | 711 KB |
| `02_bajar_overview.py` | reads the 160 m overview over the extent | ~3.7 MB |
| `03_verificar_overview.py` | checks unit norm and georeferencing | ~1 MB |
| `04_agregar_ageb.py` | builds the 431 × 64 AGEB table | local |
| `05_tamizaje.py` | the two cosine questions, plus sensitivity | local |

Total transfer is about **4.4 MB**, against the **1.20 GB** a full-resolution
year over this extent would cost.

## Three traps, and why the code asserts rather than assumes

1. **The COGs are stored bottom-up.** Opening a `.tiff` directly returns north
   and south swapped, which would hand every AGEB the embedding of its
   *mirrored* location with nothing downstream looking wrong. Everything here
   goes through the `.vrt`, and refuses to continue if the y resolution is not
   negative.
2. **De-quantization is `((v/127.5)**2) * sign(v)`** — squared and
   sign-preserving, not a linear rescale. A linear one leaves the vectors off
   the unit sphere and distorts every cosine similarity computed from them.
3. **The VRTs reference their sources over `/vsis3/`**, so anonymous S3 access
   must be enabled or GDAL retries without credentials until it gives up.

The STAC index is deliberately not used: reading it needs `pyarrow`, and each
tile's `.vrt` already carries its SRS and GeoTransform in the first 1.2 KB, so
ranged reads over all 520 tiles cost less than the 4.99 MB index.

## Attribution

Required by the dataset's CC-BY 4.0 licence:

> The AlphaEarth Foundations Satellite Embedding dataset is produced by Google
> and Google DeepMind.

Citation: Brown, Kazmierski, Pasquarella et al. (2025), arXiv:2507.22291.
