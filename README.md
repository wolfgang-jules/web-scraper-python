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

- La lista de páginas se llama `links` (lista de objetos).
- Cada objeto de `links` contiene:
  - `url`: la URL a scrapear.
  - `page_title_selector`: selector CSS para obtener el título de la página.
  - `specification_block`: mismo esquema que antes (`section_title_selector`, `section_content_selector`).

## Ejecución

Desde la terminal, ejecuta:

```ps
python main.py --config config.json
```

-- El scraper descargará las secciones encontradas y las imágenes de cada página definida en `links`.
-- Los datos se guardarán en `output/data/{brand}.json` (la clave principal contiene `pages`).
-- Las imágenes se guardarán en `output/images/{Brand}/{Page_Title}/`.

## Notas

- El scraper está diseñado para ser fácilmente extensible y mantenible.
- Si necesitas scrapear otra marca, crea un nuevo archivo de configuración siguiendo la misma estructura.
- El scraper no interpreta ni filtra el contenido: solo refleja la estructura HTML encontrada.
- El código está preparado para agregar soporte a Playwright en el futuro.
