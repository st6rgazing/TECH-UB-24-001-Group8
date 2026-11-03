"""MISE app skeleton: browser (frontend) -> Flask (backend) -> Postgres (database).

Reads DATABASE_URL from the environment (.env locally, Railway Variables in production).
User input (bakery + product + weekday) goes to the backend, which runs the SQL and renders the page.
"""
import os

import psycopg2
from dotenv import load_dotenv
from flask import Flask, render_template, request

load_dotenv()
app = Flask(__name__)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def query(sql, params=()):
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@app.route("/")
def index():
    bakeries = query("SELECT bakery_id, name FROM bakeries ORDER BY bakery_id")
    bakery_id = int(request.args.get("bakery", bakeries[0][0]))
    bakery_name = dict(bakeries)[bakery_id]

    # COUNT: how big is this bakery's history
    tickets, first_day, last_day = query(
        "SELECT count(*), min(sold_at)::date, max(sold_at)::date FROM tickets WHERE bakery_id = %s", (bakery_id,))[0]

    # SUM: top ten products by units sold
    top = query("""
        SELECT p.name, SUM(ti.quantity) AS units, COUNT(DISTINCT t.ticket_id) AS tickets
        FROM ticket_items ti
        JOIN tickets  t ON t.ticket_id = ti.ticket_id
        JOIN products p ON p.product_id = ti.product_id
        WHERE t.bakery_id = %s
        GROUP BY p.name ORDER BY units DESC LIMIT 10""", (bakery_id,))

    # AVG: for the chosen product, average units sold per open day, by weekday (the model's baseline)
    product = request.args.get("product") or top[0][0]
    by_weekday = query("""
        WITH daily AS (
            SELECT t.sold_at::date AS d, SUM(ti.quantity) AS units
            FROM ticket_items ti
            JOIN tickets  t ON t.ticket_id = ti.ticket_id
            JOIN products p ON p.product_id = ti.product_id
            WHERE t.bakery_id = %s AND p.name = %s
            GROUP BY t.sold_at::date)
        SELECT EXTRACT(ISODOW FROM d)::int AS dow, ROUND(AVG(units), 1) AS avg_units, COUNT(*) AS days
        FROM daily GROUP BY dow ORDER BY dow""", (bakery_id, product))
    weekday_rows = [(WEEKDAYS[d - 1], avg, days) for d, avg, days in by_weekday]

    # AVG by hour: when during the day the chosen product sells (the intraday curve)
    by_hour = query("""
        SELECT EXTRACT(HOUR FROM t.sold_at)::int AS h, SUM(ti.quantity) AS units
        FROM ticket_items ti
        JOIN tickets  t ON t.ticket_id = ti.ticket_id
        JOIN products p ON p.product_id = ti.product_id
        WHERE t.bakery_id = %s AND p.name = %s
        GROUP BY h ORDER BY h""", (bakery_id, product))
    peak_hour = max(by_hour, key=lambda r: r[1])[0] if by_hour else None

    return render_template("index.html", bakeries=bakeries, bakery_id=bakery_id, bakery_name=bakery_name,
                           tickets=tickets, first_day=first_day, last_day=last_day, top=top,
                           product=product, products=[r[0] for r in top], weekday_rows=weekday_rows,
                           by_hour=by_hour, peak_hour=peak_hour)


@app.route("/health")
def health():
    return {"ok": True, "bakeries": query("SELECT count(*) FROM bakeries")[0][0]}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5080)), debug=True)
