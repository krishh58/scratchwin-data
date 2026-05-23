"""Minnesota Lottery — scratch game prize tables (server-rendered, requests only).
Game list at /games/scratch has 41 card.card--games divs with name, price, href, game#.
Individual game pages have full prize/odds tables with total prize counts.
Note: MN does not publish per-tier remaining counts; total counts are used.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

_BASE = "https://www.mnlottery.com"
_GAMES_URL = f"{_BASE}/games/scratch"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_prize_table(soup: BeautifulSoup) -> list[dict]:
    table = soup.find("table")
    if not table:
        return []
    tiers = []
    for row in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        # cells[0] = "To Win$1,000"   cells[-1] = "Number of Prizes**12"
        prize_m = re.search(r"\$([\d,]+)", cells[0])
        count_m = re.search(r"([\d,]+)\s*$", cells[-1])
        if not prize_m or not count_m:
            continue
        prize = int(prize_m.group(1).replace(",", ""))
        total = int(count_m.group(1).replace(",", ""))
        if prize > 0 and total > 0:
            tiers.append({"prize": prize, "remaining": total, "total": total})
    tiers.sort(key=lambda t: t["prize"], reverse=True)
    return tiers


def scrape() -> list[dict]:
    r = requests.get(_GAMES_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    tickets = []
    for card in soup.find_all("div", class_="card--games"):
        try:
            # Name
            name_el = card.find(class_="card--lottery-headline")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Price
            price_el = card.find(class_="lottery-details")
            price_m = re.search(r"\$([\d.]+)", price_el.get_text(strip=True) if price_el else "")
            price = float(price_m.group(1)) if price_m else 0.0
            if price <= 0:
                continue

            # Detail page URL
            img_a = card.find("div", class_="card-image-wrapper")
            href = img_a.find("a")["href"] if img_a and img_a.find("a") else ""
            if not href:
                continue

            # Game number from image alt (e.g. "2091 Breakthe Bank Mini 524x349")
            img = card.find("img")
            game_num = ""
            image_url = None
            if img:
                if img.get("alt"):
                    num_m = re.match(r"^(\d+)\s", img["alt"].strip())
                    game_num = num_m.group(1) if num_m else ""
                src = img.get("src") or img.get("data-src", "")
                if src:
                    image_url = src if src.startswith("http") else f"https://www.mnlottery.com{src}"
            if not game_num:
                slug = href.rstrip("/").split("/")[-1]
                trail_m = re.search(r"-(\d{3,5})$", slug)
                game_num = trail_m.group(1) if trail_m else slug

            # Fetch game detail page
            gr = requests.get(href, headers=HEADERS, timeout=15)
            gr.raise_for_status()
            gsoup = BeautifulSoup(gr.text, "html.parser")
            tiers = _parse_prize_table(gsoup)

            if not tiers:
                continue

            total_prize_value = sum(t["prize"] * t["total"] for t in tiers)
            total_tickets = int(total_prize_value / (0.65 * price)) if price > 0 else 0

            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": total_tickets,
                "gameNumber": game_num,
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })

            time.sleep(0.4)

        except Exception as e:
            print(f"[MN] Error on {name if 'name' in dir() else '?'}: {e}")

    return tickets
