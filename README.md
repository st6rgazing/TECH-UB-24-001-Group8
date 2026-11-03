# MISE — TECH-UB 24 Group 8

Bakery sell-out predictor: tells bakery staff when to bake and how much, before items sell out.

This repo holds the **database skeleton** and **application skeleton** (due 2026-11-03).

```
browser  →  Flask (app.py)  →  Postgres on Railway
            templates/index.html     db/schema.sql
```

## Layout

| Path | What |
|---|---|
| `db/schema.sql` | CREATE statements for the MISE tables (bakeries, products, tickets, ticket_items + placeholder app_users, bake_plans) |
| `db/load_data.py` | Creates the tables and loads the two sample datasets into Railway Postgres |
| `app.py` | Flask backend: COUNT / SUM / AVG queries over the sales tables |
| `templates/index.html` | Frontend: pick a bakery and product, see top sellers, weekday baseline, hour-of-day curve |
| `Dockerfile` | Railway build: gunicorn on `0.0.0.0:$PORT` |
| `data/` | Sample CSVs (git-ignored): Kaggle French bakery daily sales, Kaggle The Bread Basket |

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # paste Railway's DATABASE_PUBLIC_URL
python3 db/load_data.py         # creates tables + loads data (use --reset to reload)
python3 app.py                  # http://localhost:5080
```

## Deploy on Railway

1. New project → add **Postgres**.
2. Add a service from this repo (Dockerfile is picked up automatically).
3. Service → Variables → `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`.
4. Service → Settings → Networking → **Generate Domain**.
5. From a laptop, load the data once: `DATABASE_URL=<DATABASE_PUBLIC_URL> python3 db/load_data.py`.

Never commit `.env` or paste the database URL anywhere public.
