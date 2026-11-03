"""Create the MISE schema on Postgres (DATABASE_URL from .env) and load the two bakery datasets.

    python3 db/load_data.py            # create tables + load both CSVs, print row counts
    python3 db/load_data.py --reset    # drop everything first

Sources (kept in data/, git-ignored):
    data/french_bakery_sales.csv   Kaggle "French bakery daily sales": per-line tickets with time, item, quantity, price
    data/bread_basket.csv          Kaggle "The Bread Basket" (Edinburgh): Date, Time, Transaction, Item (one row per unit)
"""
import csv, os, sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL") or sys.exit("DATABASE_URL missing: put Railway's DATABASE_PUBLIC_URL in .env")
if "railway.internal" in DATABASE_URL:
    sys.exit("That is the PRIVATE Railway host (only works inside Railway). Use DATABASE_PUBLIC_URL on a laptop.")

NOT_GOODS = {"COUPE", ".", "", "NONE", "ADJUSTMENT", "AFTERNOON WITH THE BAKER",   # register noise, not products
             "CAFE OU EAU", "DIVERS BOULANGERIE", "DIVERS PATISSERIE", "DIVERS VIENNOISERIE", "DIVERS CONFISERIE",
             "DIVERS SANDWICHS", "ARTICLE 295", "SACHET VIENNOISERIE", "PLAT", "BOISSON 33CL", "THE", "CHOCOLAT",
             "REDUCTION SUCREES 12", "REDUCTION SUCREES 24", "PLATPREPARE6,50", "PLATPREPARE5,50", "PLATPREPARE7,00",
             "PLATPREPARE6,00", "PLAT 6.50E", "PLAT 7.00", "PLAT 7.60E", "PLAT 8.30E"}

def read_french():
    """Yield (ticket_ref, sold_at, product, qty, price). The export wraps each row in quotes; prices look like '0,90 €'."""
    with open(ROOT / "data" / "french_bakery_sales.csv", newline="", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        for line in r:
            inner = line[0] if len(line) == 1 else ",".join(line)
            parts = next(csv.reader([inner]))
            if len(parts) < 7:
                continue
            _, d, t, ticket, article, qty, price = parts[:7]
            try:
                q = float(qty); p = float(price.replace("€", "").replace(",", ".").strip())
            except ValueError:
                continue
            name = article.strip().upper()
            if q <= 0 or name in NOT_GOODS:
                continue
            yield str(int(float(ticket))), f"{d} {t}:00", name, q, p

def read_bread_basket():
    """One row per unit sold; collapse to (ticket, product) -> quantity."""
    agg = Counter(); when = {}
    with open(ROOT / "data" / "bread_basket.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["Item"].strip()
            if name.upper() in NOT_GOODS:
                continue
            key = (row["Transaction"].strip(), name)
            agg[key] += 1
            when[row["Transaction"].strip()] = f'{row["Date"]} {row["Time"]}'
    for (ticket, name), q in agg.items():
        yield ticket, when[ticket], name, q, None

def load_bakery(cur, bakery_id, rows):
    products, tickets, items = {}, {}, []
    pending_products, pending_tickets = set(), {}
    buffered = []
    for ticket_ref, sold_at, name, qty, price in rows:
        pending_products.add(name); pending_tickets.setdefault(ticket_ref, sold_at)
        buffered.append((ticket_ref, name, qty, price))
    execute_values(cur, "INSERT INTO products (bakery_id, name) VALUES %s ON CONFLICT (bakery_id, name) DO NOTHING",
                   [(bakery_id, n) for n in pending_products])
    cur.execute("SELECT name, product_id FROM products WHERE bakery_id = %s", (bakery_id,)); products = dict(cur.fetchall())
    execute_values(cur, "INSERT INTO tickets (bakery_id, ticket_ref, sold_at) VALUES %s ON CONFLICT (bakery_id, ticket_ref) DO NOTHING",
                   [(bakery_id, ref, at) for ref, at in pending_tickets.items()], page_size=5000)
    cur.execute("SELECT ticket_ref, ticket_id FROM tickets WHERE bakery_id = %s", (bakery_id,)); tickets = dict(cur.fetchall())
    execute_values(cur, "INSERT INTO ticket_items (ticket_id, product_id, quantity, unit_price) VALUES %s",
                   [(tickets[ref], products[name], qty, price) for ref, name, qty, price in buffered], page_size=5000)
    return len(pending_products), len(pending_tickets), len(buffered)

def main():
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        if "--reset" in sys.argv:
            for t in ["bake_plans", "app_users", "ticket_items", "tickets", "products", "bakeries"]:
                cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        cur.execute((ROOT / "db" / "schema.sql").read_text())
        cur.execute("SELECT count(*) FROM ticket_items")
        if cur.fetchone()[0]:
            print("ticket_items already has rows; use --reset to reload"); return
        for name, country, currency, source, reader in [
            ("French bakery (Kaggle)", "France", "EUR", "Kaggle: French bakery daily sales, 2021-01-01 to 2022-09-30", read_french),
            ("The Bread Basket, Edinburgh", "United Kingdom", "GBP", "Kaggle: The Bread Basket, 2016-10-30 to 2017-04-09", read_bread_basket)]:
            cur.execute("INSERT INTO bakeries (name, country, currency, source) VALUES (%s,%s,%s,%s) ON CONFLICT (name) DO UPDATE SET source = EXCLUDED.source RETURNING bakery_id",
                        (name, country, currency, source))
            bid = cur.fetchone()[0]
            p, t, i = load_bakery(cur, bid, reader())
            print(f"{name}: {p} products, {t} tickets, {i} ticket lines")
        # placeholder rows so the placeholder tables are not empty
        cur.execute("INSERT INTO app_users (bakery_id, name, role) VALUES (1,'Demo Owner','owner'),(1,'Demo Baker','baker') ON CONFLICT DO NOTHING")
        print()
        for t in ["bakeries", "products", "tickets", "ticket_items", "app_users", "bake_plans"]:
            cur.execute(f"SELECT count(*) FROM {t}"); print(f"{t:<14}{cur.fetchone()[0]:>8} rows")

if __name__ == "__main__":
    main()
