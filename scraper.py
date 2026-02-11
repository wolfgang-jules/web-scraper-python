import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional

# --- Utility Functions ---
def safe_filename(name: str) -> str:
    """Normalize string for use as a filename or folder name."""
    if not name:
        return 'unnamed'
    s = name.strip().lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[<>:"/\\|?*]+', '_', s)
    s = re.sub(r'[^A-Za-z0-9_.-]', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('._')
    return s[:200] or 'unnamed'


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def download_image(url: str, dest_path: str, timeout: int = 10) -> bool:
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[WARN] Failed to download {url}: {e}")
        return False


def get_file_extension(url: str) -> str:
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower().lstrip('.')
    return ext


# --- Scraper Core ---
class Scraper:
    def __init__(self, config_path: str):
        with open(config_path, encoding='utf-8') as f:
            self.config = json.load(f)
        self.brand = self.config['brand']
        self.data_dir = self.config['output']['data_dir']
        self.image_dir = self.config['output']['image_dir']
        ensure_dir(self.data_dir)
        ensure_dir(self.image_dir)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; WebScraper/1.0)'})

    def scrape(self):
        pages: List[Dict[str, Any]] = []
        all_products: List[Dict[str, Any]] = []

        for page in self.config.get('links', []):
            page_url = page.get('url')
            print(f"[INFO] Scraping: {page_url}")
            soup = self.fetch_soup(page_url)
            if not soup:
                continue

            page_title = self.extract_page_title(soup, page.get('page_title_selector'))
            if not page_title:
                parsed = urlparse(page_url or '')
                fallback = (parsed.netloc + parsed.path) if parsed.netloc or parsed.path else page_url
                page_title = fallback or 'unnamed'
                print(f"[WARN] Page title not found for {page_url}; using fallback '{page_title}'")

            print(f"[INFO] Page: {page_title}")
            page_result: Dict[str, Any] = {
                'url': page_url,
                'page_title': page_title,
            }

            if self.is_listing_page(page):
                products = self.extract_listing_products(soup, page)
                print(f"[INFO] Products found: {len(products)}")

                if self.config.get('detail'):
                    self.enrich_products_with_details(products)

                page_result['products'] = products
                all_products.extend(products)
            else:
                specifications = self.process_extract_rules(soup, self.config.get('extract', []))
                image_blocks = self.config.get('images', [])
                if isinstance(image_blocks, dict):
                    image_blocks = image_blocks.get('sources', [])
                images = self.process_image_blocks(soup, page_url, image_blocks)
                page_result['specifications'] = specifications
                page_result['images'] = images

            pages.append(page_result)

        self.save_output(pages, all_products)

    def fetch_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            print(f"[ERROR] Could not fetch {url}: {e}")
            return None

    def is_listing_page(self, page_cfg: Dict[str, Any]) -> bool:
        selectors = page_cfg.get('selectors', {})
        return page_cfg.get('type') == 'listing' or bool(selectors.get('product_container'))

    def extract_listing_products(self, soup: BeautifulSoup, page_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        selectors = page_cfg.get('selectors', {})
        product_container_sel = selectors.get('product_container')
        fields = selectors.get('fields', [])

        if not product_container_sel:
            return []

        products: List[Dict[str, Any]] = []
        base_url = page_cfg.get('url', '')

        for container in soup.select(product_container_sel):
            item: Dict[str, Any] = {}
            for field in fields:
                key = field.get('key')
                if not key:
                    continue
                item[key] = self.extract_field_value(container, field, base_url)

            if not item.get('product_name') and item.get('name'):
                item['product_name'] = item.get('name')

            detail_url = item.get('detail_url')
            if isinstance(detail_url, str) and detail_url:
                item['detail_url'] = urljoin(base_url, detail_url)

            products.append(item)

        return products

    def extract_field_value(self, container: BeautifulSoup, field_cfg: Dict[str, Any], base_url: str) -> Any:
        selector = field_cfg.get('selector')
        mode = field_cfg.get('mode', 'text')
        multiple = bool(field_cfg.get('multiple', False))
        normalize_url = bool(field_cfg.get('normalize_url', False))

        if not selector:
            return [] if multiple else None

        nodes = container.select(selector)
        if not nodes:
            return [] if multiple else None

        def read(node):
            if mode == 'text':
                return node.get_text(strip=True)
            if mode == 'attr':
                attr = field_cfg.get('attr', 'href')
                value = node.get(attr)
                if value and normalize_url:
                    value = urljoin(base_url, value)
                return value
            return node.get_text(strip=True)

        if multiple:
            return [v for v in (read(n) for n in nodes) if v not in (None, '')]

        value = read(nodes[0])
        return value

    def enrich_products_with_details(self, products: List[Dict[str, Any]]):
        for product in products:
            detail_url = product.get('detail_url')
            if not detail_url:
                continue

            print(f"[INFO] Detail: {detail_url}")
            soup = self.fetch_soup(detail_url)
            if not soup:
                continue

            current_name = product.get('product_name') or product.get('name')
            detail_name = self.extract_detail_product_name(soup)
            if self.should_replace_product_name(current_name, detail_name):
                product['product_name'] = detail_name

            detail_data = self.extract_detail_data(soup, product.get('product_name'))
            product.update(detail_data)

            images = self.extract_images_from_config(soup, detail_url, product.get('product_name'))
            if images:
                product['images'] = images

    def normalize_text(self, value: Optional[str]) -> str:
        if value is None:
            return ''
        return re.sub(r'\s+', ' ', str(value)).strip()

    def looks_like_product_description(self, value: Optional[str]) -> bool:
        text = self.normalize_text(value)
        if not text:
            return False

        words = text.split()
        if len(words) >= 12:
            return True

        if len(words) >= 8 and any(ch in text for ch in '.!?'):
            return True

        return False

    def should_replace_product_name(self, current_name: Optional[str], candidate_name: Optional[str]) -> bool:
        current = self.normalize_text(current_name)
        candidate = self.normalize_text(candidate_name)

        if not candidate:
            return False

        if not current:
            return True

        if candidate.casefold() == current.casefold():
            return False

        current_is_description = self.looks_like_product_description(current)
        candidate_is_description = self.looks_like_product_description(candidate)

        # Keep short "title-like" names over long marketing descriptions.
        if candidate_is_description and not current_is_description:
            return False

        if current_is_description and not candidate_is_description:
            return True

        return len(candidate) < len(current)

    def extract_detail_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        detail_cfg = self.config.get('detail', {})
        selectors_cfg = detail_cfg.get('selectors', {})
        name_rules = selectors_cfg.get('product_name', [])

        for rule in name_rules:
            value = self.extract_field_value(soup, rule, '')
            if isinstance(value, list):
                value = value[0] if value else None
            if value:
                return value

        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        return None

    def extract_detail_data(self, soup: BeautifulSoup, product_name: Optional[str]) -> Dict[str, Any]:
        detail_cfg = self.config.get('detail', {})
        rules = detail_cfg.get('extract', [])
        result: Dict[str, Any] = {}

        for rule in rules:
            key = rule.get('key')
            if not key:
                continue

            mode = rule.get('mode', 'container')
            if mode == 'grouped_sections':
                result[key] = self.extract_grouped_sections(soup, rule, product_name)
            elif mode == 'paired_headings_paragraphs':
                result[key] = self.extract_paired_headings_paragraphs(soup, rule)
            else:
                result[key] = self.process_extract_rules(soup, [rule]).get(key, [])

        return result

    def extract_grouped_sections(self, soup: BeautifulSoup, rule: Dict[str, Any], product_name: Optional[str]) -> List[Dict[str, Any]]:
        container_sel = rule.get('container_selector')
        section_container_sel = rule.get('section_container_selector')
        title_sel = rule.get('section_title_selector')
        content_rules = rule.get('section_content_rules', [])
        ignore_patterns = [re.compile(p) for p in rule.get('ignore_if_title_matches', [])]
        skip_only_title = bool(rule.get('skip_sections_where_only_title_is_product_name', False))

        containers = soup.select(container_sel) if container_sel else [soup]
        sections_out: List[Dict[str, Any]] = []

        for container in containers:
            sections = container.select(section_container_sel) if section_container_sel else [container]
            for section in sections:
                title = None
                if title_sel:
                    title_el = section.select_one(title_sel)
                    if title_el:
                        title = title_el.get_text(strip=True)

                if title and any(p.search(title) for p in ignore_patterns):
                    continue

                items: List[str] = []
                for content_rule in content_rules:
                    c_mode = content_rule.get('mode', 'text')
                    c_sel = content_rule.get('selector')
                    if not c_sel:
                        continue

                    if c_mode == 'list':
                        for el in section.select(c_sel):
                            txt = el.get_text(strip=True)
                            if txt:
                                items.append(txt)
                    elif c_mode == 'text':
                        for el in section.select(c_sel):
                            txt = el.get_text(strip=True)
                            if txt:
                                items.append(txt)
                    elif c_mode == 'table':
                        for table in section.select(c_sel):
                            rows = table.find_all('tr')
                            if rows:
                                for row in rows:
                                    row_text = ' '.join(td.get_text(strip=True) for td in row.find_all(['td', 'th']))
                                    if row_text:
                                        items.append(row_text)
                            else:
                                txt = table.get_text(strip=True)
                                if txt:
                                    items.append(txt)

                if skip_only_title and title and product_name and title.strip() == str(product_name).strip() and not items:
                    continue

                if title or items:
                    sections_out.append({
                        'title': title,
                        'items': items,
                    })

        return sections_out

    def extract_paired_headings_paragraphs(self, soup: BeautifulSoup, rule: Dict[str, Any]) -> List[Dict[str, str]]:
        container_sel = rule.get('container_selector')
        title_sel = rule.get('title_selector')
        text_sel = rule.get('text_selector')

        containers = soup.select(container_sel) if container_sel else [soup]
        pairs: List[Dict[str, str]] = []

        for container in containers:
            titles = [el.get_text(strip=True) for el in container.select(title_sel)] if title_sel else []
            texts = [el.get_text(strip=True) for el in container.select(text_sel)] if text_sel else []
            max_len = max(len(titles), len(texts), 0)

            for i in range(max_len):
                title = titles[i] if i < len(titles) else ''
                text = texts[i] if i < len(texts) else ''
                if title or text:
                    pairs.append({'title': title, 'text': text})

        return pairs

    def process_extract_rules(self, soup: BeautifulSoup, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process `extract` rules from config and return a dict keyed by rule `key`."""
        result: Dict[str, Any] = {}
        for rule in rules:
            key = rule.get('key')
            container_sel = rule.get('container_selector')
            extract_mode = rule.get('extract_mode', 'container')
            children = rule.get('children', [])
            collected = []

            if not container_sel:
                containers = [soup]
            else:
                containers = soup.select(container_sel)

            for c in containers:
                if extract_mode == 'container':
                    item = {}
                    for child in children:
                        ckey = child.get('key')
                        sel = child.get('selector')
                        mode = child.get('extract_mode', 'text')
                        if not sel:
                            item[ckey] = None
                            continue
                        el = c.select_one(sel)
                        if not el:
                            item[ckey] = None
                            continue
                        if mode == 'text':
                            item[ckey] = el.get_text(strip=True)
                        elif mode == 'recursive':
                            values: List[str] = []
                            for li in el.find_all('li'):
                                txt = li.get_text(strip=True)
                                if txt:
                                    values.append(txt)
                            if not values:
                                for row in el.find_all('tr'):
                                    txt = ' '.join(td.get_text(strip=True) for td in row.find_all(['td', 'th']))
                                    if txt:
                                        values.append(txt)
                            if not values:
                                txt = el.get_text(strip=True)
                                values = [txt] if txt else []
                            item[ckey] = values
                        else:
                            item[ckey] = el.get_text(strip=True)
                    collected.append(item)
                else:
                    collected.append(c.get_text(strip=True))

            result[key] = collected
        return result

    def extract_images_from_config(self, soup: BeautifulSoup, base_url: str, product_name: Optional[str]) -> Dict[str, List[str]]:
        image_cfg = self.config.get('images', {})
        if not isinstance(image_cfg, dict):
            return {}

        sources = image_cfg.get('sources', [])
        if not sources:
            return {}

        download_flag = bool(image_cfg.get('download', False))
        allowed_exts = set(ext.lower() for ext in image_cfg.get('allowed_extensions', []))
        naming = image_cfg.get('naming', 'image_{index}')

        folders_cfg = image_cfg.get('folders', {})
        brand_folder_tpl = folders_cfg.get('brand_folder', '{brand}')
        product_folder_tpl = folders_cfg.get('product_folder', '{product_name_sanitized}')

        token_values = {
            'brand': safe_filename(self.brand),
            'product_name_sanitized': safe_filename(str(product_name or 'unnamed')),
        }

        brand_folder = safe_filename(brand_folder_tpl.format(**token_values))
        product_folder = safe_filename(product_folder_tpl.format(**token_values))
        out_dir = os.path.join(self.image_dir, brand_folder, product_folder)

        result: Dict[str, List[str]] = {}
        image_index = 1

        for source in sources:
            key = source.get('key', 'images')
            container_sel = source.get('container_selector')
            image_sel = source.get('image_selector', 'img')
            mode = source.get('mode', 'attr')
            attr = source.get('attr', 'src')

            containers = soup.select(container_sel) if container_sel else [soup]
            collected: List[str] = []

            for container in containers:
                for node in container.select(image_sel):
                    if mode == 'attr':
                        value = node.get(attr) or node.get('src') or node.get('data-src')
                    else:
                        value = node.get_text(strip=True)

                    if not value:
                        continue

                    image_url = urljoin(base_url, value)
                    ext = get_file_extension(image_url) or 'jpg'
                    if allowed_exts and ext.lower() not in allowed_exts:
                        continue

                    if download_flag:
                        ensure_dir(out_dir)
                        base_name = naming.format(index=image_index)
                        file_name = f"{safe_filename(base_name)}.{ext}"
                        image_path = os.path.join(out_dir, file_name)
                        if download_image(image_url, image_path):
                            rel = os.path.relpath(image_path, '.').replace('\\', '/')
                            collected.append(rel)
                            image_index += 1
                    else:
                        collected.append(image_url)
                        image_index += 1

            result[key] = collected

        return result

    def process_image_blocks(self, soup: BeautifulSoup, base_url: str, image_blocks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Legacy support: process image blocks list and optionally download images."""
        images_result: Dict[str, List[str]] = {}
        for block in image_blocks:
            key = block.get('key', 'images')
            container_sel = block.get('container_selector')
            img_sel = block.get('image_selector', 'img')
            download_flag = block.get('download', False)
            collected: List[str] = []

            if container_sel:
                containers = soup.select(container_sel)
            else:
                containers = [soup]

            img_count = 1
            brand_dir = safe_filename(self.brand)
            for c in containers:
                for img in c.select(img_sel):
                    src = img.get('src') or img.get('data-src') or img.get('data-original')
                    if not src:
                        continue
                    img_url = urljoin(base_url, src)
                    if download_flag:
                        ext = get_file_extension(img_url) or 'jpg'
                        out_dir = os.path.join(self.image_dir, brand_dir, safe_filename(base_url))
                        ensure_dir(out_dir)
                        img_filename = f"{key}_{img_count}.{ext}"
                        img_path = os.path.join(out_dir, img_filename)
                        if download_image(img_url, img_path):
                            rel = os.path.relpath(img_path, '.').replace('\\', '/')
                            collected.append(rel)
                            img_count += 1
                    else:
                        collected.append(img_url)

            images_result[key] = collected

        return images_result

    def extract_page_title(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        if selector:
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)

        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        title_tag = soup.title
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)

        return None

    def save_output(self, pages: List[Dict[str, Any]], products: Optional[List[Dict[str, Any]]] = None):
        out_path = os.path.join(self.data_dir, f"{safe_filename(self.brand)}.json")
        ensure_dir(os.path.dirname(out_path))
        data: Dict[str, Any] = {
            'brand': self.brand,
            'pages': pages,
        }
        if products:
            data['products'] = products

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Output saved to {out_path}")
