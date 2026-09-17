# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC
# MAGIC Run this once. It takes about a minute.
# MAGIC
# MAGIC Six raw files shipped with this repo. This notebook lands them in a Unity Catalog
# MAGIC volume and registers each one as a **bronze** table — bronze meaning *exactly as it
# MAGIC arrived*, wrong types and missing values included. Cleaning it up is your job,
# MAGIC starting in the next notebook.
# MAGIC
# MAGIC Nothing to configure. Press **Run all**.

# COMMAND ----------

import os
import shutil
import time
from pathlib import Path

CATALOG = "workspace"
SCHEMA = "media_lab"
VOLUME = "raw"

VOL = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

# The data folder is a sibling of this notebook's folder inside the Git folder.
# A notebook's working directory is its own folder, so this resolves wherever the
# repo was cloned and whatever the account email is.
DATA = Path(os.getcwd()).parent / "data"

if not DATA.exists():
    raise FileNotFoundError(
        f"Could not find the data folder at {DATA}.\n\n"
        "This notebook has to run from inside the cloned Git folder, next to the\n"
        "data/ directory. If you copied the notebook somewhere else, go back to the\n"
        "Git folder in the workspace file browser and open it from there."
    )

print(f"repo data : {DATA}")
print(f"target    : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. A place to put it
# MAGIC
# MAGIC A **schema** to hold tables, and a **volume** to hold files. A volume is the
# MAGIC landing zone: governed storage for anything that is not yet a table.

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

print(f"schema ready : {CATALOG}.{SCHEMA}")
print(f"volume ready : {VOL}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Land the files
# MAGIC
# MAGIC Three formats, because real landing zones are never uniform: CSV exports from
# MAGIC operational systems, Parquet for the high-volume event feeds, JSON for anything
# MAGIC that came out of an app.

# COMMAND ----------

t0 = time.time()
for path in sorted(DATA.iterdir()):
    if path.name.startswith("."):
        continue
    shutil.copyfile(path, f"{VOL}/{path.name}")
    print(f"  {path.stat().st_size / 1_048_576:>7.2f} MB  {path.name}")
print(f"\nlanded in {time.time() - t0:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Register them as bronze tables
# MAGIC
# MAGIC One rule for this layer: **change nothing**. The CSV columns stay strings because
# MAGIC that is how a CSV arrives. Duplicate rows stay duplicated. If a value is missing,
# MAGIC it stays missing.
# MAGIC
# MAGIC That discipline is what makes the next notebook honest — you can always prove what
# MAGIC the source actually said, separately from what you decided it meant.

# COMMAND ----------

# `inferSchema=false` is the whole point here: it keeps every CSV column a string
# instead of quietly guessing types, so nothing is repaired before you have seen it.
CSV_SOURCES = {
    "bronze_content": "content.csv",
    "bronze_households": "households.csv",
    "bronze_advertisers": "advertisers.csv",
}
PARQUET_SOURCES = {
    "bronze_playback_events": "playback_events.parquet",
    "bronze_ad_impressions": "ad_impressions.parquet",
}
JSON_SOURCES = {
    "bronze_viewer_feedback": "viewer_feedback.jsonl",
}

COMMENTS = {
    "bronze_content": "Programming catalog, as exported from the scheduling system. CSV, so every column is text.",
    "bronze_households": "Subscribing households, as exported from billing. CSV, so every column is text.",
    "bronze_advertisers": "Advertisers buying ad inventory, as exported from the sales system. CSV, so every column is text.",
    "bronze_playback_events": "Playback telemetry as landed from the event feed. Timestamps arrive as strings, platform is sometimes absent, and at-least-once delivery means a session can land more than once.",
    "bronze_ad_impressions": "One row per ad slot opportunity, as landed from the billing export. Monetary columns arrive as text.",
    "bronze_viewer_feedback": "Free-text viewer feedback from app reviews, support tickets, surveys and social. Ratings arrive as strings and some records omit a field entirely.",
}

t0 = time.time()

for table, filename in CSV_SOURCES.items():
    (spark.read.format("csv")
     .option("header", "true")
     .option("inferSchema", "false")
     .load(f"{VOL}/{filename}")
     .write.mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.{table}"))

for table, filename in PARQUET_SOURCES.items():
    (spark.read.parquet(f"{VOL}/{filename}")
     .write.mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.{table}"))

for table, filename in JSON_SOURCES.items():
    (spark.read.json(f"{VOL}/{filename}")
     .write.mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.{table}"))

for table, comment in COMMENTS.items():
    escaped = comment.replace("'", "''")
    spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA}.{table} IS '{escaped}'")

print(f"six bronze tables built in {time.time() - t0:.1f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check
# MAGIC
# MAGIC If every row below has a count, you are ready.

# COMMAND ----------

EXPECTED = {
    "bronze_content": 88,
    "bronze_households": 3_000,
    "bronze_advertisers": 40,
    "bronze_playback_events": 300_900,
    "bronze_ad_impressions": 180_000,
    "bronze_viewer_feedback": 400,
}

problems = []
print(f"{'table':<26} {'rows':>10} {'expected':>10}")
print("-" * 50)
for table, expected in EXPECTED.items():
    actual = spark.table(f"{CATALOG}.{SCHEMA}.{table}").count()
    flag = "" if actual == expected else "   <-- unexpected"
    print(f"{table:<26} {actual:>10,} {expected:>10,}{flag}")
    if actual != expected:
        problems.append(f"{table}: got {actual:,}, expected {expected:,}")

print()
if problems:
    raise AssertionError(
        "Setup did not produce the expected data:\n  " + "\n  ".join(problems)
        + "\n\nRe-run this notebook from the top. If it still disagrees, tell the "
          "instructor — every number in the workshop is keyed to these counts."
    )

print("=" * 50)
print("  READY.  Open 01_find_the_bugs next.")
print("=" * 50)
