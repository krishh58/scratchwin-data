"""Vermont Lottery — single outstanding-prizes page with top tier data + total tickets."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.vtlottery.com/games/instant-tickets/outstanding-prizes"
GAME_URL = "https://www.vtlottery.com/games/instant-tickets"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _build_image_map() -> dict[str, str]:
    """Fetch a single game page — VT embeds all instant-ticket images there."""
    try:
        # Outstanding-prizes page has links to individual game pages
        r = requests.get(URL, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        excluded = {"/games/instant-tickets", "/games/instant-tickets/outstanding-prizes",
                    "/games/instant-tickets/last-day-to-redeem"}
        link = soup.find("a", href=re.compile(r"/games/instant-tickets/[^/]+$"))
        while link and link["href"] in excluded:
            link = link.find_next("a", href=re.compile(r"/games/instant-tickets/[^/]+$"))
        if not link:
            return {}
        game_page_url = "https://www.vtlottery.com" + link["href"]
        r2 = requests.get(game_page_url, headers=HEADERS, timeout=20)
        all_paths = re.findall(
            r'sites/default/files/instant-tickets/[^\s"\'<>]+\.(?:jpg|jpeg|png)',
            r2.text, re.I
        )
        img_map: dict[str, str] = {}
        for path in all_paths:
            decoded = requests.utils.unquote(path)
            m = re.search(r'\b(\d{4})\b', decoded)
            if m:
                gnum = m.group(1)
                if gnum not in img_map:
                    img_map[gnum] = f"https://www.vtlottery.com/{path}"
        return img_map
    except Exception:
        return {}


def _parse_money(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s) else 0


def scrape() -> list[dict]:
    img_map = _build_image_map()
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    # Header: Price | Game # | Game Name | Top Prizes | Unclaimed Top Prizes | Total Unclaimed | % Sold | # Of Tickets
    rows = table.find_all("tr")
    tickets = []
    current: dict | None = None

    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 6:
            continue

        # Main game row: price in col 0
        if cells[0].startswith("$"):
            price = float(_parse_money(cells[0]))
            game_num = cells[1]
            name = cells[2]
            top_prizes_raw = cells[3]   # e.g. "$75,000$35,000$5,000$1,000$500"
            unclaimed_raw = cells[4]    # e.g. "4219130284"
            total_unclaimed = _parse_money(cells[5]) if len(cells) > 5 else 0
            pct_sold = float(cells[6]) if len(cells) > 6 and cells[6] else 0.0
            total_tickets = _parse_money(cells[7]) if len(cells) > 7 else 0

            top_prize_amounts = [_parse_money(p) for p in re.split(r"\$", top_prizes_raw) if re.search(r"\d", p)]
            top_prize_counts = [int(x) for x in re.findall(r"\d+", unclaimed_raw)]

            tiers = []
            for i, amt in enumerate(top_prize_amounts):
                rem = top_prize_counts[i] if i < len(top_prize_counts) else 0
                if amt > 0:
                    tiers.append({"prize": amt, "remaining": rem, "total": rem})
            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                current = None
                continue

            pct_remaining = max(0.0, 100.0 - pct_sold) / 100.0
            remaining_tickets = int(total_tickets * pct_remaining) if total_tickets > 0 else 0

            current = {
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": remaining_tickets,
                "gameNumber": game_num,
                "tiers": tiers,
            }
            if game_num and game_num in img_map:
                current["imageUrl"] = img_map[game_num]
            tickets.append(current)

        elif current and not cells[0].startswith("$"):
            # Continuation row — extra prize tier for same game
            top_prizes_raw = cells[3] if len(cells) > 3 else ""
            unclaimed_raw = cells[4] if len(cells) > 4 else ""
            amounts = [_parse_money(p) for p in re.split(r"\$", top_prizes_raw) if re.search(r"\d", p)]
            counts = [int(x) for x in re.findall(r"\d+", unclaimed_raw)]
            for i, amt in enumerate(amounts):
                rem = counts[i] if i < len(counts) else 0
                if amt > 0:
                    current["tiers"].append({"prize": amt, "remaining": rem, "total": rem})
            current["tiers"].sort(key=lambda t: t["prize"], reverse=True)

    return tickets
