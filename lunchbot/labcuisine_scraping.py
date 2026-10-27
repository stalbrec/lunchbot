import logging
import requests
import yaml
from bs4 import BeautifulSoup

from lunchbot.utils import generate_hash

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

from urllib.parse import urljoin
import io
import zipfile
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Berlin")
DISH_ELEMENT_SEP = " / "


def docx_tables(contents: bytes):
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    str_content = zipfile.ZipFile(io.BytesIO(contents)).read("word/document.xml")
    root = ET.fromstring(str_content)

    tbls = list(root.iter(W + "tbl"))
    cells = [
        [
            [
                DISH_ELEMENT_SEP.join(
                    filter(
                        None,
                        (
                            "".join(t.text or "" for t in p.iter(W + "t")).strip()
                            for p in tc.iter(W + "p")
                        ),
                    )
                )
                for tc in tr.iter(W + "tc")
            ]
            for tr in tbl.iter(W + "tr")
        ]
        for tbl in tbls
    ]
    return cells


def fetch_todays_lunch_menu(url: str):
    """Fetch todays menu from the labcuisine website

    Parameters
    ----------
    url : str
        URL of the labcuisine menu website

    Returns
    -------
    list
        List of dictionaries with the dishes, prices and info
        Example: [{"name": "Dish 1", "price": "€4.50", "info": "vegan"}, ...]
    """
    dishes_list = []

    page_source = requests.get(url, timeout=20).text

    soup = BeautifulSoup(page_source, "html.parser")
    docx_a = soup.select_one('a.wp-block-file__button[href$=".docx"]')
    if docx_a is None:
        raise ValueError(f"No menu docx link found on {url}!")
    docx_url = urljoin(url, docx_a["href"])
    try:
        docx_response = requests.get(docx_url, timeout=20)
        docx_response.raise_for_status()
        tables = docx_tables(docx_response.content)
        last_modified = parsedate_to_datetime(docx_response.headers.get("Last-Modified"))
        last_modified = (
            last_modified if last_modified.tzinfo else last_modified.replace(tzinfo=timezone.utc)
        )
        assert len(tables) != 0 and len(tables) >= 2
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        detail = docx_response.text[:500] if docx_response is not None else ""
        raise RuntimeError(f"Labcuisine menu retrieval failed: {exc!r} {detail}".strip()) from exc
    now = datetime.now(TZ)
    # now = datetime(year=2026, month=10, day=7, tzinfo=TZ)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # 2-day grace period; since menu is often uploaded on the previous weekend
    this_week = last_modified >= week_start - timedelta(days=2)
    if not this_week:
        raise RuntimeError("Extracted menu is not this weeks menu!")

    weekday_index = datetime.now().weekday()+1

    for category_row in tables[1][1:]:
        if len(category_row) <= weekday_index:
            continue
        if category_row[0] == "canteen":
            continue

        dish_elements = category_row[weekday_index].split(DISH_ELEMENT_SEP)
        assert len(dish_elements) > 0

        dish_name = dish_elements[0]
        dish_price = ""
        for e in dish_elements:
            if "€" in e:
                dish_price = e.strip().replace(",", ".")

        if any(veg in category_row[0].lower() for veg in ["vegetarian", "vegetarisch"]):
            dish_info = "vegetarian"
        elif "vegan" in category_row[0].lower():
            dish_info = "vegan"
        else:
            dish_info = "meat"

        dishes_list.append(
            {
                "name": dish_name_translated,
                "info": dish_info,
                "price": dish_price,
                "canteen": "Labcuisine",
                "hash": generate_hash(dish_name),
            }
        )
    return dishes_list


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    url = "https://www.labcuisine.de/menu/"
    todays_menu = fetch_todays_lunch_menu(url)
    print(todays_menu)
