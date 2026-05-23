"""Indiana (Hoosier) Lottery — HTML scraping, full tier data. Non-www domain required."""
import re
import time
import requests
from bs4 import BeautifulSoup

STATS_URL = "https://hoosierlottery.com/games/scratch-off/scratch-off-stats/"
BASE_URL = "https://hoosierlottery.com/games/scratch-off"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://hoosierlottery.com/",
}


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def _name_to_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _get_game_list() -> list[tuple[str, str, float, str]]:
    """Returns (slug, name, price, game_number) from stats page."""
    resp = requests.get(STATS_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    hdrs = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    name_idx = next((i for i, h in enumerate(hdrs) if "name" in h), 0)
    num_idx = next((i for i, h in enumerate(hdrs) if "number" in h), 1)
    price_idx = next((i for i, h in enumerate(hdrs) if "price" in h), 5)

    games = []
    seen = set()
    for row in table.find_all("tr")[1:]:
        cols = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cols) < 3:
            continue
        name = cols[name_idx].strip()
        game_num = re.sub(r"[^\d]", "", cols[num_idx])
        price = float(_parse_money(cols[price_idx]) or 0) if price_idx < len(cols) else 0.0
        slug = _name_to_slug(name)
        if slug and slug not in seen and name:
            seen.add(slug)
            games.append((slug, name, price, game_num))

    return games


def _scrape_game(slug: str, name: str, price: float, game_num: str) -> dict | None:
    try:
        url = f"{BASE_URL}/{slug}/"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find prize table: Prize Amount | Unclaimed | Total Winning Tickets
        table = None
        for t in soup.find_all("table"):
            hdrs = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any("unclaimed" in h or "remaining" in h for h in hdrs):
                table = t
                break

        if not table:
            return None

        hdrs = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        prize_idx = next((i for i, h in enumerate(hdrs) if "prize" in h and "amount" in h), 0)
        unclaimed_idx = next((i for i, h in enumerate(hdrs) if "unclaimed" in h or "remaining" in h), None)
        total_idx = next((i for i, h in enumerate(hdrs) if "total" in h), None)

        if unclaimed_idx is None:
            return None

        tiers = []
        for row in table.find_all("tr")[1:]:
            cols = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
            prize = _parse_money(cols[prize_idx])
            remaining = _parse_money(cols[unclaimed_idx]) if unclaimed_idx < len(cols) else 0
            total = _parse_money(cols[total_idx]) if total_idx is not None and total_idx < len(cols) else remaining
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers or price <= 0:
            return None

        # Grab ticket image — getmedia GUIDs are in the HTML
        image_url = None
        imgs = re.findall(r'(getmedia/[a-f0-9-]+/[^"\'?&\s]+\.(?:png|jpg|jpeg))', resp.text, re.I)
        # Filter out promo/banner images; prefer ones with game number in filename
        for img_path in imgs:
            fname = img_path.split("/")[-1].lower()
            if any(x in fname for x in ["logo", "banner", "header", "icon", "bg-", "background"]):
                continue
            image_url = f"https://hoosierlottery.com/{img_path}"
            break

        entry = {
            "name": name,
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": game_num or slug,
            "tiers": tiers,
        }
        if image_url:
            entry["imageUrl"] = image_url
        return entry
    except Exception:
        return None


def scrape() -> list[dict]:
    games = _get_game_list()
    tickets = []
    for slug, name, price, game_num in games:
        result = _scrape_game(slug, name, price, game_num)
        if result:
            tickets.append(result)
        time.sleep(0.3)
    return tickets
