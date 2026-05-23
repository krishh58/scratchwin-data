"""North Carolina Education Lottery — HTML scraping (game list + per-game detail)."""
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.nclottery.com"
LIST_URL = "https://www.nclottery.com/scratch-off"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nclottery.com/",
}


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def _slug_to_name(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def _get_game_links() -> list[tuple[str, str, float]]:
    """Returns list of (url, name, price) for all games on listing page."""
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    games = []
    seen = set()
    for link in soup.find_all("a", href=re.compile(r"/scratch-off/\d+/")):
        href = link["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)

        # Name from URL slug (last path segment)
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        name = _slug_to_name(slug)

        # Price from tile CSS class: price_20, price_5, etc.
        tile = link.find_parent(class_=re.compile(r"tile"))
        price = 0.0
        if tile:
            for cls in tile.get("class", []):
                m = re.match(r"price_(\d+)", cls)
                if m:
                    price = float(m.group(1))
                    break

        games.append((href, name, price))

    return games


def _scrape_game(url: str, name: str, price: float) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find prize table: headers Value | Odds | Total | Remaining
        table = None
        for t in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any("remaining" in h for h in headers) and any("value" in h or "prize" in h for h in headers):
                table = t
                break

        if not table:
            return None

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        val_idx = next((i for i, h in enumerate(headers) if "value" in h or "prize" in h), 0)
        total_idx = next((i for i, h in enumerate(headers) if "total" in h), None)
        rem_idx = next((i for i, h in enumerate(headers) if "remaining" in h), None)

        if rem_idx is None:
            return None

        tiers = []
        for row in table.find_all("tr")[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            # Skip disclaimer rows (span a single merged cell)
            if len(cols) < 3:
                continue
            if not re.search(r"\$", cols[val_idx] if val_idx < len(cols) else ""):
                continue
            prize = _parse_money(cols[val_idx])
            remaining = _parse_money(cols[rem_idx]) if rem_idx < len(cols) else 0
            total = _parse_money(cols[total_idx]) if total_idx is not None and total_idx < len(cols) else remaining
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers or price <= 0:
            return None

        game_num = re.search(r"/scratch-off/(\d+)/", url)
        gid = game_num.group(1) if game_num else ""
        image_url = f"https://www.nclottery.com/Content/Images/Instant/nc{gid}_sqr.png" if gid else None
        return {
            "name": name,
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": gid,
            "tiers": tiers,
            **({"imageUrl": image_url} if image_url else {}),
        }
    except Exception:
        return None


def scrape() -> list[dict]:
    games = _get_game_links()
    tickets = []
    for url, name, price in games:
        result = _scrape_game(url, name, price)
        if result:
            tickets.append(result)
        time.sleep(0.3)
    return tickets
