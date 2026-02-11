# Copilot instructions for web-scraper-python

Purpose: short, actionable guidance so an AI coding agent can be productive immediately.

Quick start
- **Install deps:** `pip install -r requirements.txt`
- **Run:** `python main.py --config config-verifone.json` (default config file)
- **Python:** target Python 3.7+

Big picture
- Single-process scraper: `main.py` is the runner that instantiates `Scraper` from [main.py](main.py#L1-L20) and calls `scrape()`.
- All scraping logic lives in `scraper.py` (`Scraper` class) — loading config, fetching pages, extracting data, downloading images, and saving JSON output. See [scraper.py](scraper.py#L1-L60).

Config-driven patterns (key points)
- Config is JSON and controls everything: `brand`, `output`, `links`, `detail`, `images`.
- `links` is a list of page descriptors. Each link may be a listing or a detail page. Key fields: `url`, `type` (optional, e.g. `listing`), `page_title_selector`, and `selectors`.
- Listing `selectors` uses `product_container` and `fields` (each field: `key`, `selector`, `mode`=`text|attr`, `attr`, `multiple`, `normalize_url`). The scraper calls `extract_listing_products` to map these.
- Detail extraction is configured under `detail` with `selectors` and `extract` rules. Supported extract modes: `grouped_sections`, `keyed_sections`, `repeat`, `pairs`, `paired_headings_paragraphs`, plus generic `container` children handled in `process_extract_rules`.
- Images: two related systems exist: modern `images` dict with `sources`, `download`, `allowed_extensions`, `naming`, and `folders` (`path_folder`, `brand_folder`, `product_folder`), and legacy `image_blocks` processed by `process_image_blocks`.

Important behaviors & conventions
- URLs are normalized using `urljoin` before storage; detail URLs are preferred as dedup keys.
- Deduplication order: `detail_url` → `product_name` → `listing_image_url` → raw product JSON (see `product_dedup_key`).
- Filenames and folders use `safe_filename()`; templates use `{brand}` and `{product_name_sanitized}` tokens and are rendered via `render_template()`.
- Image download is disabled by default; enable via `images.download: true` to store files under the configured `image_dir`.
- Output JSON saved to `{output.data_dir}/{safe_filename(brand)}.json`; set `output.include_flat_products` to include a top-level `products` array.

Where to look for examples
- Config example referenced in [README.md](README.md#L1-L80) and `config-verifone.json` (repo root) — follow that as canonical.
- Listing extraction: see `extract_listing_products` and `extract_field_value` in [scraper.py](scraper.py#L60-L180).
- Detail extraction: see `enrich_products_with_details`, `extract_detail_data`, and `process_extract_rules` in [scraper.py](scraper.py#L180-L420).
- Image handling: see `extract_images_from_config` and `process_image_blocks` in [scraper.py](scraper.py#L420-L840).

Developer notes for edits
- Prefer extending config-driven rules over hard-coding selectors in code.
- When adding new extraction modes, update `process_extract_rules` and include tests (manual run) using a small sample config and a saved HTML snippet.
- For debugging network issues, modify `Scraper.fetch_soup` or `self.session.headers` in `Scraper.__init__`.

What an AI should avoid changing
- Do not rename config keys or change output directory semantics without updating README and sample configs.

If anything here is unclear or you want more examples (sample configs or target HTML snippets), tell me which area to expand.


## GIT
- **commit language:** Todos los mensajes de commit generados por el botón "generate commit messages" deben estar siempre en español. Usar modo imperativo para el subject (p. ej. "Añade", "Arregla", "Actualiza") y mantener el resumen breve (<= 50 caracteres) seguido de un cuerpo opcional en español.
- **Código / comentarios:** El código y los comentarios en el código deben permanecer en inglés.
- **Formato recomendado:** `Tipo: Resumen corto` donde `Tipo` es uno de: `Añade`, `Arregla`, `Mejora`, `Refactor`, `Docs`, `Test`, `Revert`.
- **Ejemplos (en español):**
	- `Añade: soporte para images.path_folder y naming` 
	- `Arregla: normalización de URLs relativas en extract_field_value`
	- `Docs: actualiza README con instrucciones de configuración`
- **Comportamiento ante dudas:** Si la extensión/acción no puede inferir el idioma o el contexto, generar un mensaje en español y añadir una nota corta en español pidiendo confirmación (p. ej. "Por favor confirmar: ¿este cambio incluye...?").
