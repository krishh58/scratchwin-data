"""Maine Lottery — summary table with top prize tiers + total unclaimed."""
import re
import requests
from bs4 import BeautifulSoup

BASE = "https://www.mainelottery.com"
URL = f"{BASE}/players_info/unclaimed_prizes.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    # "$1.00" -> 1, "$10,000.00" -> 10000
    m = re.search(r"[\d,]+", s)
    if not m:
        return 0
    return int(m.group(0).replace(",", ""))


def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    tickets = []
    current: dict | None = None

    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue

        # Main game row has price, game#, name, pct_unsold, total_unclaimed
        if cells[0].startswith("$") and cells[1].isdigit():
            m_price = re.search(r"\$([\d.]+)", cells[0])
            price = float(m_price.group(1)) if m_price else 0.0
            game_num = cells[1]
            name = cells[2]
            pct_unsold = float(cells[3]) if cells[3] else 0.0
            total_unclaimed = _parse_money(cells[4]) if len(cells) > 4 else 0

            top_prizes_str = cells[5] if len(cells) > 5 else ""
            top_unclaimed_str = cells[6] if len(cells) > 6 else ""

            top_prize_amounts = [_parse_money(p) for p in top_prizes_str.split("$") if re.search(r"\d", p)]
            top_prize_counts_raw = re.findall(r"\d+", top_unclaimed_str)
            top_prize_counts = [int(x) for x in top_prize_counts_raw]

            tiers = []
            for i, amt in enumerate(top_prize_amounts):
                rem = top_prize_counts[i] if i < len(top_prize_counts) else 0
                if amt > 0:
                    tiers.append({"prize": amt, "remaining": rem, "total": rem})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                current = None
                continue

            # Estimate total tickets: total_unclaimed is remaining prize pool
            # pct_unsold = % of tickets not yet sold (remaining)
            # remaining pool / remaining tickets ≈ avg prize per remaining ticket
            # Use 65% payout: totalPool ≈ totalTickets * price * 0.65
            # remainingPool / totalPool = pct_unsold / 100 => totalPool = remainingPool * 100 / pct_unsold
            if pct_unsold > 0 and price > 0:
                total_pool_est = total_unclaimed * 100.0 / pct_unsold
                total_tickets = int(total_pool_est / (0.65 * price))
                remaining_tickets = int(total_tickets * pct_unsold / 100.0)
            else:
                total_tickets = 0
                remaining_tickets = 0

            current = {
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": remaining_tickets,
                "gameNumber": game_num,
                "tiers": tiers,
            }
            tickets.append(current)

        elif current and cells[0] == "" and len(cells) >= 7:
            # Continuation row — additional top prize tier for same game
            top_prizes_str = cells[5] if len(cells) > 5 else ""
            top_unclaimed_str = cells[6] if len(cells) > 6 else ""
            for p_str, c_str in zip(top_prizes_str.split("$"), re.findall(r"\d+", top_unclaimed_str)):
                amt = _parse_money("$" + p_str)
                cnt = int(c_str)
                if amt > 0:
                    current["tiers"].append({"prize": amt, "remaining": cnt, "total": cnt})
            current["tiers"].sort(key=lambda t: t["prize"], reverse=True)

    return tickets
