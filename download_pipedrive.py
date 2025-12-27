import csv
import logging
import os
import random
import re
import time
from urllib.parse import urlparse

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException


OUTPUT_DIR = "downloaded_html_articles"
CSV_PATH = "article_csv.csv"
LOG_PATH = "download_articles.log"
BASE_DELAY_SECONDS = 2
JITTER_SECONDS = 1.5
PAGE_LOAD_TIMEOUT = 30


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def filename_for(link_text: str, url: str, existing_names: set, used_names: set) -> str:
    slug = slugify(link_text)
    if not slug:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        slug = slugify(path.replace("/", "-")) or "home"
    name = f"{slug}.html"
    if name in existing_names:
        return name
    if name in used_names:
        index = 2
        while True:
            candidate = f"{slug}-{index}.html"
            if candidate not in existing_names and candidate not in used_names:
                name = candidate
                break
            index += 1
    used_names.add(name)
    return name


def is_valid_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if not os.path.exists(CSV_PATH):
        logging.error("Missing CSV file: %s", CSV_PATH)
        return

    with open(CSV_PATH, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        logging.error("CSV file is empty: %s", CSV_PATH)
        return

    existing_names = set()
    for entry in os.listdir(OUTPUT_DIR):
        if entry.lower().endswith(".html"):
            existing_names.add(entry)

    driver = uc.Chrome()
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    used_names = set()
    try:
        for index, row in enumerate(rows, start=1):
            link_text = (row.get("link_text") or "").strip()
            url = (row.get("full_url") or "").strip()

            if not is_valid_url(url):
                logging.error("Skipping invalid URL at row %d: %s", index, url)
                continue

            filename = filename_for(link_text, url, existing_names, used_names)
            output_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(output_path):
                logging.info("Skipping existing file: %s", output_path)
                continue

            try:
                logging.info("Downloading (%d/%d): %s", index, len(rows), url)
                driver.get(url)
                html = driver.page_source
                with open(output_path, "w", encoding="utf-8") as out:
                    out.write(html)
                logging.info("Saved: %s", output_path)
                existing_names.add(filename)
            except TimeoutException:
                logging.error("Timeout while downloading: %s", url)
            except WebDriverException as exc:
                logging.error("WebDriver error for %s: %s", url, exc)
            except OSError as exc:
                logging.error("File write error for %s: %s", url, exc)

            delay = BASE_DELAY_SECONDS + random.uniform(0, JITTER_SECONDS)
            time.sleep(delay)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
