-- =====================================================================
--  MISE — database skeleton (Deployed database skeleton, due 2026-11-03)
--  Bakery sell-out predictor: what the backend needs to answer
--  "how much of each item will sell today, and by when".
-- =====================================================================
--
--  ENTITIES
--    bakery        a shop whose point-of-sale data we hold
--    product       one thing a bakery sells (croissant, baguette, ...)
--    ticket        one checkout at the register (receipt)
--    ticket_item   one line on a receipt: product x quantity x price
--    app_user      placeholder: a bakery staff login (not final)
--    bake_plan     placeholder: what the model recommends baking (not final)
--
--  RELATIONSHIPS (all one-to-many, so foreign keys, no bridge tables)
--    bakery  1 --< product        a bakery sells many products
--    bakery  1 --< ticket         a bakery rings up many tickets
--    ticket  1 --< ticket_item    a ticket has many lines
--    product 1 --< ticket_item    a product appears on many tickets
--    bakery  1 --< app_user       staff belong to one bakery
--    bakery  1 --< bake_plan      plans are per bakery and product
--
--  KEYS
--    every table has a generated integer key; the register's own receipt
--    number is kept as ticket_ref and is unique only within a bakery
--
--  DATA LOADED BY db/load_data.py
--    bakery 1  French bakery (Kaggle, 2021-01-01 → 2022-09-30): 136k tickets, 234k lines, prices
--    bakery 2  The Bread Basket, Edinburgh (Kaggle, 2016-10-30 → 2017-04-09): 9.5k tickets, 21k lines, no prices
--
--  Parents first so the file runs top to bottom.
-- =====================================================================

CREATE TABLE IF NOT EXISTS bakeries (
    bakery_id   SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    country     TEXT,
    currency    TEXT,
    source      TEXT                                   -- where the data came from
);

CREATE TABLE IF NOT EXISTS products (
    product_id  SERIAL PRIMARY KEY,
    bakery_id   INTEGER NOT NULL REFERENCES bakeries(bakery_id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    category    TEXT,                                  -- bread / viennoiserie / drink ... (filled later)
    lead_time_min SMALLINT,                            -- minutes from "start batch" to "on the shelf" (entered by the bakery)
    UNIQUE (bakery_id, name)
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   SERIAL PRIMARY KEY,
    bakery_id   INTEGER NOT NULL REFERENCES bakeries(bakery_id) ON DELETE CASCADE,
    ticket_ref  TEXT    NOT NULL,                      -- the register's receipt number
    sold_at     TIMESTAMP NOT NULL,                    -- wall-clock time at the shop (timezone-unaware on purpose)
    UNIQUE (bakery_id, ticket_ref)
);

CREATE TABLE IF NOT EXISTS ticket_items (
    item_id     SERIAL PRIMARY KEY,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(ticket_id)   ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    quantity    NUMERIC(8,2) NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(8,2)                           -- NULL where the source has no prices
);

-- Placeholders for tables the final product will need (shape only; not final).
CREATE TABLE IF NOT EXISTS app_users (
    user_id     SERIAL PRIMARY KEY,
    bakery_id   INTEGER REFERENCES bakeries(bakery_id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    role        TEXT CHECK (role IN ('owner','baker','staff')),
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bake_plans (
    plan_id     SERIAL PRIMARY KEY,
    bakery_id   INTEGER NOT NULL REFERENCES bakeries(bakery_id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    plan_date   DATE    NOT NULL,
    predicted_demand NUMERIC(8,2),
    planned_qty      NUMERIC(8,2),
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (bakery_id, product_id, plan_date)
);

-- Indexes for the queries the app runs: sales by product, by day, by hour.
CREATE INDEX IF NOT EXISTS idx_tickets_bakery_time   ON tickets(bakery_id, sold_at);
CREATE INDEX IF NOT EXISTS idx_items_product         ON ticket_items(product_id);
CREATE INDEX IF NOT EXISTS idx_items_ticket          ON ticket_items(ticket_id);
