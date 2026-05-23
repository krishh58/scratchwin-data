"""Kentucky Lottery — JS-embedded game data + per-game HTML prize tables."""
import re
import time
import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.kylottery.com/apps/scratch_offs/index.html"
BASE_URL = "https://www.kylottery.com/apps/scratch_offs/games"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.kylottery.com/",
}


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", str(text)) or "0")


def _get_game_list() -> list[tuple[str, str, float]]:
    """Parse game slugs and names from parallel JS arrays in the page."""
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    text = resp.text

    names = re.findall(r'availableGames\.push\("([^"]+)"\)', text)
    slugs = re.findall(r'availableGamesDtl\.push\("[^"]*games/([A-Za-z0-9_]+)"', text)

    games = []
    seen = set()
    for name, slug in zip(names, slugs):
        if slug in seen:
            continue
        seen.add(slug)
        # Name format: "$750,000 Extravaganza - 139" — strip trailing " - NNN"
        clean_name = re.sub(r"\s*-\s*\d+$", "", name).strip()
        games.append((slug, clean_name, 0.0))  # price fetched from detail page

    return games


def _scrape_game(slug_num: str, name: str, price: float) -> dict | None:
    try:
        url = f"{BASE_URL}/{slug_num}"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        if price <= 0:
            price_m = re.search(r"Value:\s*\$(\d+(?:\.\d+)?)", soup.get_text(), re.I)
            if price_m:
                price = float(price_m.group(1))

        table = None
        for t in soup.find_all("table"):
            hdrs = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any("remaining" in h for h in hdrs):
                table = t
                break

        if not table:
            return None

        hdrs = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        prize_idx = next((i for i, h in enumerate(hdrs) if "amount" in h or "prize" in h), 0)
        remaining_idx = next((i for i, h in enumerate(hdrs) if "remaining" in h), None)
        total_idx = next((i for i, h in enumerate(hdrs) if "total" in h), None)

        if remaining_idx is None:
            return None

        tiers = []
        for row in table.find_all("tr")[1:]:
            cols = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
            prize = _parse_money(cols[prize_idx])
            remaining = _parse_money(cols[remaining_idx]) if remaining_idx < len(cols) else 0
            total = _parse_money(cols[total_idx]) if total_idx is not None and total_idx < len(cols) else remaining
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": max(total, remaining)})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers or price <= 0:
            return None

        game_num = re.search(r"_(\d+)$", slug_num)
        gnum = game_num.group(1) if game_num else slug_num

        image_url = None
        gallery_imgs = re.findall(
            r'(/export/kylmod/galleries/images/KYLottery_ScratchOffs/[^\s"\'<>]+\.(?:jpg|jpeg|png))',
            resp.text, re.I
        )
        if gallery_imgs:
            image_url = "https://www.kylottery.com" + gallery_imgs[0]

        entry = {
            "name": name,
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": gnum,
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
    for slug_num, name, price in games:
        result = _scrape_game(slug_num, name, price)
        if result:
            tickets.append(result)
        time.sleep(0.3)
    return tickets
