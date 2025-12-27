import csv
import logging
import random
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException


BASE_URL = "https://fanteziigreieriprostii.ro/"
PAGE_LOAD_TIMEOUT = 30
BASE_DELAY_SECONDS = 2
JITTER_SECONDS = 1.5
OUTPUT_CSV = "article_csv.csv"

CATEGORY_PAGES = [
    ("https://fanteziigreieriprostii.ro/category/poezie/", 7),
    ("https://fanteziigreieriprostii.ro/category/unde-atingi/", 5),
    ("https://fanteziigreieriprostii.ro/category/poezie/fantezii/", 4),
    ("https://fanteziigreieriprostii.ro/category/poezie/greieri/", 5),
    ("https://fanteziigreieriprostii.ro/category/poezie/prostii/", 1),
    (
        "https://fanteziigreieriprostii.ro/category/unde-atingi/"
        "ludic-mistic-senzual-si-carnal/ludic-mistic-senzual/",
        1,
    ),
]


class FeaturedImageLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_overlay = False
        self.overlay_depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            classes = attrs.get("class", "")
            if "featured-image-overlay" in classes.split():
                self.in_overlay = True
                self.overlay_depth = 1
                return
            if self.in_overlay:
                self.overlay_depth += 1
        if self.in_overlay and tag == "a":
            href = attrs.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if self.in_overlay and tag == "div":
            self.overlay_depth -= 1
            if self.overlay_depth <= 0:
                self.in_overlay = False
                self.overlay_depth = 0


def is_fantezii_domain(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    return parsed.netloc.lower().endswith("fanteziigreieriprostii.ro")


def normalize_link(href: str) -> str:
    return urljoin(BASE_URL, href)


def extract_post_links(html_text: str):
    parser = FeaturedImageLinkParser()
    parser.feed(html_text)
    results = []
    seen = set()

    for href in parser.links:
        full_url = normalize_link(href.strip())
        if not is_fantezii_domain(full_url):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        results.append(full_url)

    return results


def page_url_for(base_url: str, page_number: int) -> str:
    if page_number == 1:
        return base_url
    return f"{base_url}page/{page_number}/"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    all_links = []
    seen_urls = set()

    driver = uc.Chrome()
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    try:
        for base_url, max_page in CATEGORY_PAGES:
            for page_number in range(1, max_page + 1):
                page_url = page_url_for(base_url, page_number)
                logging.info("Scraping posts from %s", page_url)
                try:
                    driver.get(page_url)
                    html_text = driver.page_source
                except TimeoutException:
                    logging.warning("Timeout while loading %s", page_url)
                    continue
                except WebDriverException as exc:
                    logging.warning("WebDriver error for %s: %s", page_url, exc)
                    continue

                links = extract_post_links(html_text)
                for url in links:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_links.append(url)

                delay = BASE_DELAY_SECONDS + random.uniform(0, JITTER_SECONDS)
                time.sleep(delay)
    finally:
        driver.quit()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["post_url"])
        for url in all_links:
            writer.writerow([url])

    logging.info("Saved %d unique post links to %s", len(all_links), OUTPUT_CSV)


if __name__ == "__main__":
    main()
