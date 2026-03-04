#!/usr/bin/env python3
"""Scrape rental apartments in Stockholm from qasa.com using Playwright."""

import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://qasa.com/se/sv/find-home?homeTypes=apartment&searchAreas=Stockholm~~se"
OUTPUT_FILE = "apartments.json"


def extract_from_graphql(responses):
    """Extract apartment data from intercepted GraphQL responses."""
    apartments = []
    seen_ids = set()

    for data in responses:
        # Navigate into common GraphQL response shapes
        homes = []
        if isinstance(data, dict):
            # Try common paths: data.homeSearch.filterHomesOffset.nodes,
            # data.homeSearch.edges, data.homes, etc.
            for key in ("data", ):
                if key in data:
                    data = data[key]
                    break

            # Recursively find lists that look like apartment listings
            homes = _find_home_nodes(data)

        for home in homes:
            apt = _parse_home_node(home)
            if apt and apt.get("link") and apt["link"] not in seen_ids:
                seen_ids.add(apt["link"])
                apartments.append(apt)

    return apartments


def _find_home_nodes(obj, depth=0):
    """Recursively search a nested dict/list for arrays of home-like objects."""
    if depth > 8:
        return []

    if isinstance(obj, list):
        # Check if this looks like a list of homes
        if len(obj) > 0 and isinstance(obj[0], dict) and _looks_like_home(obj[0]):
            return obj
        # Search deeper
        for item in obj:
            result = _find_home_nodes(item, depth + 1)
            if result:
                return result

    elif isinstance(obj, dict):
        # Check "nodes", "edges", "homes", "results" keys first
        for key in ("nodes", "edges", "homes", "results", "filterHomesOffset"):
            if key in obj:
                result = _find_home_nodes(obj[key], depth + 1)
                if result:
                    return result
        # Then check "node" inside edges
        if "node" in obj:
            result = _find_home_nodes(obj["node"], depth + 1)
            if result:
                return [result] if isinstance(result, dict) else result
        # Scan all values
        for val in obj.values():
            if isinstance(val, (dict, list)):
                result = _find_home_nodes(val, depth + 1)
                if result:
                    return result

    return []


def _looks_like_home(obj):
    """Heuristic: does this dict look like a home listing?"""
    if not isinstance(obj, dict):
        return False
    keys = set(obj.keys())
    home_keys = {"rent", "address", "location", "sqm", "rooms", "id",
                 "numberOfRooms", "squareMeters", "monthlyCost", "monthlyRent",
                 "title", "slug", "currency", "type", "homeType"}
    # If it has a node wrapper (edges pattern), look inside
    if "node" in keys and isinstance(obj["node"], dict):
        return _looks_like_home(obj["node"])
    return len(keys & home_keys) >= 2


def _parse_home_node(node):
    """Parse a single home node from the GraphQL response into a clean dict."""
    if not isinstance(node, dict):
        return None

    # Unwrap edge->node pattern
    if "node" in node and isinstance(node["node"], dict):
        node = node["node"]

    def _get(*paths):
        """Try multiple attribute paths, return first non-None."""
        for path in paths:
            val = node
            for key in path.split("."):
                if isinstance(val, dict):
                    val = val.get(key)
                else:
                    val = None
                    break
            if val is not None:
                return val
        return None

    rent = _get("rent", "monthlyCost", "monthlyRent",
                "monthlyCostCents", "rentInclusion.rent",
                "cost.monthlyCost", "cost.rent")
    sqm = _get("squareMeters", "sqm", "size", "livingArea",
               "area", "numberOfSquareMeters")
    rooms = _get("numberOfRooms", "rooms", "roomCount")

    # Build address
    street = _get("location.streetAddress", "location.street",
                  "address.street", "street", "location.route")
    area = _get("location.area", "location.locality", "location.city",
                "area", "location.district")
    address = street or area or _get("title", "displayTitle")
    if street and area and street != area:
        address = f"{street}, {area}"

    # Build link
    slug = _get("slug", "id")
    link = _get("url", "link", "href")
    if not link and slug:
        link = f"https://qasa.com/se/sv/home/{slug}"

    if not any([rent, sqm, rooms, address]):
        return None

    return {
        "rent": rent,
        "size_sqm": sqm,
        "rooms": rooms,
        "address": address,
        "link": link,
    }


def extract_from_dom(page):
    """Fallback: extract apartment data by scraping the rendered DOM."""
    apartments = []

    # Try multiple possible selectors for listing cards
    selectors = [
        "a[href*='/home/']",
        "[data-testid*='home']",
        "[class*='ListingCard']",
        "[class*='listing-card']",
        "[class*='HomeCard']",
        "[class*='home-card']",
        "article a",
    ]

    cards = []
    for sel in selectors:
        cards = page.query_selector_all(sel)
        if len(cards) > 2:
            print(f"  Found {len(cards)} cards with selector: {sel}")
            break

    if not cards:
        print("  No listing cards found in DOM. Dumping page for debugging...")
        # Save page HTML for debugging
        html = page.content()
        with open("debug_page.html", "w") as f:
            f.write(html)
        print("  Saved page HTML to debug_page.html")
        return apartments

    seen = set()
    for card in cards:
        try:
            href = card.get_attribute("href") or ""
            if "/home/" not in href:
                # If the card itself isn't a link, find the link inside
                link_el = card.query_selector("a[href*='/home/']")
                if link_el:
                    href = link_el.get_attribute("href") or ""

            if not href or href in seen:
                continue
            seen.add(href)

            link = href if href.startswith("http") else f"https://qasa.com{href}"
            text = card.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            apt = {
                "rent": None,
                "size_sqm": None,
                "rooms": None,
                "address": None,
                "link": link,
            }

            for line in lines:
                low = line.lower()
                # Rent: look for "kr" or number patterns
                if "kr" in low and apt["rent"] is None:
                    import re
                    m = re.search(r"[\d\s]+", line.replace("\xa0", " "))
                    if m:
                        apt["rent"] = m.group().strip().replace(" ", "")
                        try:
                            apt["rent"] = int(apt["rent"])
                        except ValueError:
                            pass
                # Size: "XX m²" or "XX kvm"
                elif ("m²" in low or "kvm" in low) and apt["size_sqm"] is None:
                    import re
                    m = re.search(r"(\d+(?:[.,]\d+)?)", line)
                    if m:
                        apt["size_sqm"] = float(m.group(1).replace(",", "."))
                # Rooms: "X rum" or "X rok"
                elif ("rum" in low or "rok" in low) and apt["rooms"] is None:
                    import re
                    m = re.search(r"(\d+)", line)
                    if m:
                        apt["rooms"] = int(m.group(1))
                # Address: first text line that isn't a number pattern
                elif apt["address"] is None and len(line) > 3 and not line[0].isdigit():
                    apt["address"] = line

            apartments.append(apt)
        except Exception as e:
            print(f"  Error parsing card: {e}")
            continue

    return apartments


def scroll_to_load_all(page, max_scrolls=50):
    """Scroll down to trigger infinite scroll / lazy loading."""
    prev_height = 0
    stable_count = 0

    for i in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)
        height = page.evaluate("document.body.scrollHeight")

        if height == prev_height:
            stable_count += 1
            if stable_count >= 3:
                print(f"  Reached bottom after {i + 1} scrolls")
                return
        else:
            stable_count = 0
        prev_height = height

    print(f"  Stopped scrolling after {max_scrolls} scrolls")


def click_load_more(page, max_clicks=30):
    """Click 'load more' / 'visa fler' button if present."""
    for i in range(max_clicks):
        btn = None
        for selector in [
            "button:has-text('Visa fler')",
            "button:has-text('Load more')",
            "button:has-text('Ladda fler')",
            "button:has-text('Fler')",
            "[data-testid*='load-more']",
            "[class*='load-more']",
        ]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    break
                btn = None
            except Exception:
                btn = None

        if not btn:
            break

        print(f"  Clicking 'load more' (click {i + 1})...")
        btn.click()
        time.sleep(2)

    return


def main():
    print("Starting Qasa apartment scraper...")
    graphql_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="sv-SE",
        )
        page = context.new_page()

        # Intercept GraphQL responses
        def handle_response(response):
            url = response.url
            if "graphql" in url.lower() or "/api" in url.lower():
                try:
                    body = response.json()
                    graphql_responses.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        print(f"Navigating to {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
        except PlaywrightTimeout:
            print("  Initial load timed out, continuing anyway...")

        # Wait a bit for any security challenge to resolve
        print("Waiting for page to settle...")
        time.sleep(5)

        # Check if we're on a challenge page
        title = page.title()
        print(f"  Page title: {title}")

        # If stuck on challenge, wait longer
        if "just a moment" in title.lower() or "checking" in title.lower():
            print("  Detected bot challenge, waiting up to 30s...")
            for _ in range(15):
                time.sleep(2)
                title = page.title()
                if "just a moment" not in title.lower() and "checking" not in title.lower():
                    break
            print(f"  Page title after wait: {title}")

        # Scroll and click load-more to get all listings
        print("Loading all listings...")
        click_load_more(page)
        scroll_to_load_all(page)

        # Wait for any final network requests
        time.sleep(3)

        # Try GraphQL data first
        apartments = []
        if graphql_responses:
            print(f"Intercepted {len(graphql_responses)} API responses, extracting data...")
            apartments = extract_from_graphql(graphql_responses)
            print(f"  Extracted {len(apartments)} apartments from API responses")

        # Fall back to DOM scraping if GraphQL didn't yield enough results
        if len(apartments) < 5:
            print("Trying DOM extraction...")
            dom_apartments = extract_from_dom(page)
            print(f"  Extracted {len(dom_apartments)} apartments from DOM")

            # Merge, preferring GraphQL data
            existing_links = {a["link"] for a in apartments}
            for apt in dom_apartments:
                if apt["link"] not in existing_links:
                    apartments.append(apt)

        browser.close()

    print(f"\nTotal apartments found: {len(apartments)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)

    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
