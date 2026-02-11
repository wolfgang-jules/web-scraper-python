# Instrucciones para ejecutar el scraper de productos de hardware

## Requisitos

- Python 3.7 o superior
- Instalar dependencias:
  - requests
  - beautifulsoup4

Puedes instalar las dependencias ejecutando:

```ps
pip install requests beautifulsoup4
```

## Configuración

1. Crea o edita el archivo `config.json` siguiendo el ejemplo incluido.
2. Asegúrate de que los selectores CSS y URLs sean correctos para la marca y las páginas que deseas scrapear.

Estructura importante del `config.json` actualizado:

- `master_page`: configuración compartida para todas las URLs (selectores, tipo de página, etc.).
- `links`: lista de URLs/categorías a scrapear reutilizando `master_page`.
  - Puede ser string (`"https://sitio/categoria"`) o objeto (`{"category": "...", "url": "..."}`).
  - Cada link puede sobrescribir partes de `master_page` si lo necesitas.
- Los selectores aceptan string o arreglos (fallback en orden): `selector` o `selectors`.
- `output.save_per_link_files`: si es `true`, guarda un JSON por link/categoría.
- `output.save_combined_file`: si es `true`, también guarda el archivo combinado de toda la marca.
- `output.root_dir`: raíz de salida (por defecto `output`), con estructura `output/{brand}/data` y `output/{brand}/images`.

## Ejecución

Desde la terminal, ejecuta:

```ps
python main.py --config config.json
```

-- El scraper descargará las secciones encontradas y las imágenes de cada página definida en `links`.
-- Los datos se guardarán en `output/{brand}/data/{brand}.json` (la clave principal contiene `pages`).
-- Si `output.save_per_link_files=true`, también se genera `output/{brand}/data/{category}.json` por cada URL.
-- Las imágenes se guardarán en `output/{brand}/images/`.

## Notas

- El scraper está diseñado para ser fácilmente extensible y mantenible.
- Si necesitas scrapear otra marca, crea un nuevo archivo de configuración siguiendo la misma estructura.
- El scraper no interpreta ni filtra el contenido: solo refleja la estructura HTML encontrada.
- El código está preparado para agregar soporte a Playwright en el futuro.
