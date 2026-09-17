# Confidence Is Not Accuracy

**The data skills behind AI you can trust.**

A model's confidence tells you nothing about whether its output is right. A wrong answer
arrives in the same fluent tone as a correct one — same formatting, same speed, same
total absence of hedging.

In this workshop you get a messy streaming-media dataset and a free Databricks account.
You'll find the bugs by hand, then watch an AI assistant do the same cleanup in about
twenty seconds. Then you'll ask it a question it gets confidently, invisibly wrong —
because the answer depends on a business rule that exists nowhere in the data. So you'll
encode the rule, ask again, and watch it get the answer right.

> Workshop at [URI CS Connect Day](https://cs-uri-edu.github.io/cs-connect-day/), Friday
> September 18, 2026, 2:00–3:30pm, Bliss Hall 290. No experience with Spark, SQL at
> scale, or the cloud required.

---

## Start here — about ten minutes

Nothing to install. No credit card. No prework.

### 1. Get a free Databricks account (~3 min)

Go to **[login.databricks.com/signup?provider=DB_FREE_TIER](https://login.databricks.com/signup?provider=DB_FREE_TIER)**
and sign up with Google, Microsoft, or an email address.

Choose **Free Edition** if you are asked. It does not expire, it never asks for a payment
method, and everything you build today is still there next month.

### 2. Clone this repo into your workspace (~2 min)

In your new workspace:

1. Click **Workspace** in the left sidebar, then your own user folder.
2. Click the **Create** button (top right) → **Git folder**.
3. Paste this URL:
   ```
   https://github.com/keithmwine/confidence-is-not-accuracy
   ```
4. Click **Create Git folder**.

You do not need a GitHub account — this repo is public, so it clones without credentials.

### 3. Run the setup notebook (~2 min)

Open **`notebooks/00_setup`** and click **Run all**.

It creates a schema, lands the six raw data files in a Unity Catalog volume, and
registers them as bronze tables. It finishes by printing `READY` and a row count for each
table. If a count disagrees with what it expected, it will tell you loudly rather than
let you start from broken data.

### 4. Open `notebooks/01_find_the_bugs`

That's it. You're running.

---

## What you'll do

| Notebook | What happens | Time |
|---|---|---|
| `00_setup` | Land six messy files, register them as bronze tables | 2 min |
| `01_find_the_bugs` | Find five real defects by hand. Duplicated rows, missing values, numbers stored as text, a timestamp that silently drops a day | 15 min |
| `02_let_the_ai_clean_it` | Give the assistant your list. Watch it fix all five correctly, fast | 10 min |
| `03_ask_a_question` | Build a Genie agent on your clean data. Ask it something. Get a confident, specific, completely wrong answer | 20 min |
| `04_encode_what_you_know` | Encode the missing business rule three ways — a catalog comment, a metric view, an agent instruction. Ask again. Get it right | 20 min |

The thing worth watching for is *when* the wrong answer shows up: after the data is
clean, not before. Cleaning was never the hard part.

---

## What's in here

```
data/            Six raw files. CSV, Parquet and JSON, because real landing zones
                 are never uniform. Committed to the repo so every person in the
                 room gets byte-identical data and identical numbers.
notebooks/       The workshop, in order.
generator/       The script that built data/. Runs locally in seconds, no cloud
                 account needed.
instructor/      Timed runbook for anyone teaching this. Contains spoilers.
```

**Spoiler warning.** `generator/generate.py` and `instructor/RUNBOOK.md` are the answer
key — they document exactly where every mistake in the data was planted and why. Both are
worth reading *after* you've worked through the notebooks. Before that, they will spoil
the good part.

---

## About the data

Every row is synthetic. The company, its three networks (Tidewater, Nova, Meridian News),
the titles, the households and the advertisers are all invented. No real viewing data,
from any company, is anywhere in this repo.

The mistakes in it are not invented. Duplicate events from at-least-once delivery, CSV
columns that arrive as text, JSON records missing a key, and a business definition that
lives in somebody's head instead of in the data — these are the four most common reasons
a confident data answer turns out to be wrong.

To rebuild it yourself:

```bash
uv run --with numpy,pandas,pyarrow generator/generate.py
```

It is deterministic: one seed, fixed operation order, and assertions that fail at
generation time if the planted mistakes stop working. The dataset covers 2026-07-20 to
2026-09-17; pass `--anchor-end YYYY-MM-DD` to move the window so that questions about
"last month" still land on real data.

---

## After the workshop

Your account stays free and your work stays put. Some places to take it:

- **Finish the exercise at the end of notebook 04** — there is a second wrong answer in
  the ad-sales data, with the same shape and a different column.
- **Break your own agent.** Try to get a wrong number out of it, then close the hole.
  This is the actual skill.
- **Bring your own data.** A CSV of anything you care about, the same four notebooks'
  worth of thinking. The question is always: *what does someone need to know that this
  data does not say?*

---

## License

[MIT](LICENSE) for the code. Do whatever you like with it, including teaching it
yourself — a credit is appreciated but not required.
