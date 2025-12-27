import csv
import logging
import random
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException


BASE_URL = "https://fanteziigreieriprostii.ro/"
LAST_PAGE = 11
PAGE_LOAD_TIMEOUT = 30
BASE_DELAY_SECONDS = 2
JITTER_SECONDS = 1.5


class NavigationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_header = False
        self.in_nav = False
        self.nav_depth = 0
        self.in_anchor = False
        self.anchor_href = None
        self.anchor_text_parts = []
        self.anchor_attrs = {}
        self.collected = []
        self._class_stack = []

        self._void_tags = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
        self._exclude_text_classes = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "header" and attrs.get("id") == "masthead":
            self.in_header = True
        if self.in_header and tag == "nav" and attrs.get("id") == "access":
            self.in_nav = True
            self.nav_depth = 1
        elif self.in_nav and tag == "nav":
            self.nav_depth += 1
        if self.in_nav and tag == "a":
            self.in_anchor = True
            self.anchor_href = attrs.get("href")
            self.anchor_text_parts = []
            self.anchor_attrs = attrs
        if self.in_anchor and tag not in self._void_tags:
            classes = attrs.get("class", "")
            self._class_stack.append(classes.split())

    def handle_endtag(self, tag):
        if self.in_nav and self.in_anchor and tag == "a":
            text = " ".join("".join(self.anchor_text_parts).split())
            self.collected.append((text, self.anchor_href, self.anchor_attrs))
            self.in_anchor = False
            self.anchor_href = None
            self.anchor_text_parts = []
            self.anchor_attrs = {}
            self._class_stack = []
        elif self.in_anchor and tag not in self._void_tags and self._class_stack:
            self._class_stack.pop()
        if self.in_nav and tag == "nav":
            self.nav_depth -= 1
            if self.nav_depth <= 0:
                self.in_nav = False
                self.nav_depth = 0
        if self.in_header and tag == "header":
            self.in_header = False

    def handle_data(self, data):
        if self.in_nav and self.in_anchor:
            if any(
                cls in self._exclude_text_classes
                for class_list in self._class_stack
                for cls in class_list
            ):
                return
            self.anchor_text_parts.append(data)


def is_fantezii_domain(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    return parsed.netloc.lower().endswith("fanteziigreieriprostii.ro")


def normalize_link(href: str) -> str:
    return urljoin(BASE_URL, href)


def should_skip_link(text: str, href: str, attrs: dict) -> bool:
    if not href or not href.strip():
        return True
    href = href.strip()
    if href.startswith("#"):
        return True
    if href.startswith(("mailto:", "tel:", "javascript:")):
        return True
    if not text:
        return True
    classes = attrs.get("class", "")
    class_list = classes.split()
    if any(cls in class_list for cls in ("site-title", "logo")):
        return True
    return False


def extract_navigation_links(html_text: str):
    parser = NavigationParser()
    parser.feed(html_text)
    results = []
    seen_urls = set()

    for text, href, attrs in parser.collected:
        if should_skip_link(text, href, attrs):
            continue
        full_url = normalize_link(href)
        if not is_fantezii_domain(full_url):
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        results.append((text, full_url))

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    all_links = []
    seen_urls = set()

    driver = uc.Chrome()
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    try:
        for page_number in range(1, LAST_PAGE + 1):
            if page_number == 1:
                page_url = BASE_URL
            else:
                page_url = f"{BASE_URL}page/{page_number}/"
            logging.info("Scraping navigation from %s", page_url)
            try:
                driver.get(page_url)
                html_text = driver.page_source
            except TimeoutException:
                logging.warning("Timeout while loading %s", page_url)
                continue
            except WebDriverException as exc:
                logging.warning("WebDriver error for %s: %s", page_url, exc)
                continue

            links = extract_navigation_links(html_text)
            for text, url in links:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_links.append((text, url))

            delay = BASE_DELAY_SECONDS + random.uniform(0, JITTER_SECONDS)
            time.sleep(delay)
    finally:
        driver.quit()

    with open("navigation_links_fantezii.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["link_text", "full_url"])
        writer.writerows(all_links)


if __name__ == "__main__":
    main()
