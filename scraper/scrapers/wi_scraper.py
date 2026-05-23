"""Wisconsin Lottery — per-game pages with top prize counts + overall odds."""
import re
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup

BASE = "https://www.wilottery.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    # "$20.00" -> 20, "$200,000" -> 200000
    m = re.search(r"[\d,]+", s)
    return int(m.group(0).replace(",", "")) if m else 0


def _get_game_slugs() -> list[tuple[str, str]]:
    """Returns list of (slug, name) for active instant games only."""
    scraper = cloudscraper.create_scraper()
    r = scraper.get(f"{BASE}/games/instant-games", timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    slugs = []
    seen: set[str] = set()
    import time as _time
    now_ts = int(_time.time())

    for item in soup.find_all("div", class_="instant-listing-item"):
        # Filter to active: data-endi far in future means no end date set
        end_ts = int(item.get("data-endi", "0"))
        if end_ts < now_ts:
            continue
        game_type = item.get("data-type", "")
        if game_type != "scratch":
            continue
        a = item.find("a", href=re.compile(r"/games/instant-games/"))
        if not a:
            continue
        href = a["href"]
        if href not in seen:
            seen.add(href)
            slugs.append((href, ""))
    return slugs


def scrape() -> list[dict]:
    slugs = _get_game_slugs()
    scraper = cloudscraper.create_scraper()
    tickets = []

    for slug, _ in slugs:
        try:
            r = scraper.get(f"{BASE}{slug}", timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Name from h1
            name_el = soup.find("h1")
            name = name_el.get_text(strip=True) if name_el else slug.split("/")[-1].replace("-", " ").title()

            # Parse instant-row divs: cell 0 = label, cell 1 = value
            info: dict[str, str] = {}
            for row in soup.find_all("div", class_="instant-row"):
                cells = [c.get_text(strip=True) for c in row.find_all("div", class_="cell")]
                if len(cells) == 2:
                    info[cells[0]] = cells[1]

            price_str = info.get("Price", "")
            if not price_str:
                continue
            m_price = re.search(r"\$([\d.]+)", price_str)
            price = float(m_price.group(1)) if m_price else 0.0
            if price <= 0:
                continue

            game_num = info.get("Game Number", slug.split("-")[-1])
            total_top = _parse_money(info.get("Total Top Prizes", "0"))
            remaining_top = _parse_money(info.get("Remaining Top Prizes", "0"))

            # Top prize amount from "top-prize" div
            top_prize_el = soup.find("div", class_="top-prize")
            top_prize_amt = 0
            if top_prize_el:
                m = re.search(r"\$([\d,]+)", top_prize_el.get_text())
                if m:
                    top_prize_amt = _parse_money(m.group(0))

            if top_prize_amt <= 0:
                continue

            # Overall odds: e.g. "1:3.1"
            odds_str = info.get("Overall Odds", "")
            odds_ratio = 0.0
            if odds_str:
                m = re.search(r"1:(\d+\.?\d*)", odds_str)
                if m:
                    odds_ratio = float(m.group(1))

            tiers = [{"prize": top_prize_amt, "remaining": remaining_top, "total": total_top}]

            # Estimate ticket counts from top prize total + odds ratio
            if total_top > 0 and odds_ratio > 0:
                # total winning tickets ≈ total_top / (top_prize_rate)
                # But we don't know top prize rate — use prize value method instead
                # totalTickets ≈ totalPrizePool / (payout * price)
                # Only have top prize pool; this will undercount — skip ticket count
                # Instead use odds: odds_ratio = totalTickets / totalWinners
                # We only know top tier winners, not all winners — can't compute directly
                pass

            total_tickets = 0
            remaining_tickets = 0

            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": remaining_tickets,
                "gameNumber": game_num,
                "tiers": tiers,
            })
            time.sleep(0.4)

        except Exception as e:
            print(f"[WI] {slug} failed: {e}")

    return tickets
