-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 01 — Find the bugs by hand
-- MAGIC
-- MAGIC You are the new data engineer at a streaming company with three networks —
-- MAGIC **Tidewater** (drama and true crime), **Nova** (sci-fi), and **Meridian News**.
-- MAGIC Six files landed overnight. Programming, sales and finance all want answers from
-- MAGIC them today.
-- MAGIC
-- MAGIC Before anybody asks this data a question, somebody has to look at it. That is this
-- MAGIC notebook. About fifteen minutes, six queries, and you will find five real defects.
-- MAGIC
-- MAGIC Run each cell, read the number, then read what it means. Do not skip ahead — the
-- MAGIC point of this notebook is that you found these yourself.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## First, just look
-- MAGIC
-- MAGIC No query technique, no aggregation. Twenty rows of the playback feed.
-- MAGIC
-- MAGIC **Spend thirty seconds actually reading them** before you run anything else. What
-- MAGIC would you check first?

-- COMMAND ----------

SELECT * FROM workspace.media_lab.bronze_playback_events LIMIT 20;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 1 — the same session arrived twice
-- MAGIC
-- MAGIC Event pipelines usually promise *at-least-once* delivery, not *exactly-once*. When
-- MAGIC a network hiccup makes a sender retry, you get the row again.

-- COMMAND ----------

SELECT
  COUNT(*)                                        AS rows_landed,
  COUNT(DISTINCT session_id)                      AS distinct_sessions,
  COUNT(*) - COUNT(DISTINCT session_id)           AS duplicates
FROM workspace.media_lab.bronze_playback_events;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **900 duplicate rows out of 300,900.** Three tenths of one percent.
-- MAGIC
-- MAGIC Small enough that no chart would look wrong, and large enough to matter if you are
-- MAGIC reporting a number to an advertiser. Nothing errored. No warning appeared. The only
-- MAGIC reason you know is that you counted two different ways and compared.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 2 — a column that is sometimes absent
-- MAGIC
-- MAGIC Which device was this played on? Usually the feed says. Sometimes it does not.

-- COMMAND ----------

SELECT
  COALESCE(platform, '** MISSING **') AS platform,
  COUNT(*)                            AS sessions
FROM workspace.media_lab.bronze_playback_events
GROUP BY 1
ORDER BY sessions DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **1,590 sessions have no platform at all.**
-- MAGIC
-- MAGIC Here is the trap in how you fix it. The obvious move is
-- MAGIC `WHERE platform IS NOT NULL`, which drops those rows — and now your total viewing
-- MAGIC is quietly 1,590 sessions short of the truth, in every report anyone builds on
-- MAGIC top of it, forever.
-- MAGIC
-- MAGIC Keeping the row and labelling the gap `'unknown'` is almost always the better
-- MAGIC answer: the total stays right, and the gap stays *visible* in every `GROUP BY`
-- MAGIC instead of silently disappearing.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 3 — numbers that are secretly text
-- MAGIC
-- MAGIC The programming catalog came from the scheduling system as a CSV. A CSV has no
-- MAGIC types. Every column arrived as a string, including the numeric ones.
-- MAGIC
-- MAGIC Before you run this: the longest thing on these networks is a three-hour live
-- MAGIC event, and the shortest is a half-hour news block. So what should `MAX` and `MIN`
-- MAGIC of `runtime_minutes` be?

-- COMMAND ----------

SELECT
  MAX(runtime_minutes)                AS max_as_text,
  MAX(CAST(runtime_minutes AS INT))   AS max_as_number,
  MIN(runtime_minutes)                AS min_as_text,
  MIN(CAST(runtime_minutes AS INT))   AS min_as_number
FROM workspace.media_lab.bronze_content;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Read that carefully. As text, the **maximum runtime is 94 and the minimum is 115**.
-- MAGIC
-- MAGIC The minimum is larger than the maximum. It is not a rounding problem or a subtle
-- MAGIC statistical artifact — sorting text puts `'94'` after `'180'` because `9` comes
-- MAGIC after `1`. The real answers are 180 and 30.
-- MAGIC
-- MAGIC No error. No null. Two confident, specific, wrong numbers.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 4 — the same problem, now about money
-- MAGIC
-- MAGIC The ad billing export has the same disease. `cpm` is what an advertiser pays per
-- MAGIC thousand impressions.

-- COMMAND ----------

SELECT
  MAX(cpm)                    AS highest_cpm_as_text,
  MAX(CAST(cpm AS DOUBLE))    AS highest_cpm_as_number
FROM workspace.media_lab.bronze_ad_impressions;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **`$9.99` versus `$67.74`.** If you reported the text answer, you would have
-- MAGIC understated your most valuable ad slot by 85%.
-- MAGIC
-- MAGIC Worth noticing: `SUM` and `AVG` on these columns come out *right*, because
-- MAGIC Databricks quietly converts text to numbers when the operation requires it.
-- MAGIC `MAX` and `MIN` do not need to convert anything to produce an answer, so they
-- MAGIC don't, and they lie. Some of your aggregates are correct and some are wrong, and
-- MAGIC the results look identical.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 5 — a timestamp that is really a string
-- MAGIC
-- MAGIC `start_ts` looks like a timestamp. Check what it actually is.

-- COMMAND ----------

SELECT
  typeof(start_ts)      AS start_ts_type,
  typeof(ingest_date)   AS ingest_date_type,
  typeof(watch_seconds) AS watch_seconds_type
FROM workspace.media_lab.bronze_playback_events
LIMIT 1;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC A string. And most of the time you will get away with it, which is what makes it
-- MAGIC dangerous.
-- MAGIC
-- MAGIC Here is a query any analyst would write to pull one month. It runs. It returns a
-- MAGIC believable number.

-- COMMAND ----------

SELECT
  COUNT_IF(start_ts BETWEEN '2026-08-01' AND '2026-08-31')      AS august_the_easy_way,
  COUNT_IF(CAST(start_ts AS TIMESTAMP) >= TIMESTAMP'2026-08-01'
       AND CAST(start_ts AS TIMESTAMP) <  TIMESTAMP'2026-09-01') AS august_actually,
  COUNT_IF(CAST(start_ts AS TIMESTAMP) >= TIMESTAMP'2026-08-01'
       AND CAST(start_ts AS TIMESTAMP) <  TIMESTAMP'2026-09-01')
    - COUNT_IF(start_ts BETWEEN '2026-08-01' AND '2026-08-31')   AS silently_dropped
FROM workspace.media_lab.bronze_playback_events;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **5,152 sessions vanished** — all of August 31st except the single instant of
-- MAGIC midnight, because as text, `'2026-08-31T20:14:03'` sorts *after* `'2026-08-31'`.
-- MAGIC
-- MAGIC 150,600 is a completely plausible answer. It is off by 3.3%, and there is nothing
-- MAGIC in the output that would tell you.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Bug 6 — a field that is not there at all
-- MAGIC
-- MAGIC Viewer feedback arrives as JSON, one record per line. JSON records are not
-- MAGIC obligated to have the same keys as each other.

-- COMMAND ----------

SELECT
  COALESCE(source_channel, '** MISSING **') AS source_channel,
  COUNT(*)                                  AS records
FROM workspace.media_lab.bronze_viewer_feedback
GROUP BY 1
ORDER BY records DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **14 of 400 records never had the key.** Not null — *absent*. Spark inferred the
-- MAGIC column from the records that did have it and gave you null for the rest, which is
-- MAGIC a reasonable guess and not the same thing as a fact.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## What you just did
-- MAGIC
-- MAGIC Six queries, five real defects:
-- MAGIC
-- MAGIC | # | Defect | Scale |
-- MAGIC |---|---|---|
-- MAGIC | 1 | Duplicate sessions from at-least-once delivery | 900 rows |
-- MAGIC | 2 | `platform` missing | 1,590 rows |
-- MAGIC | 3 | Numbers stored as text | every CSV column |
-- MAGIC | 4 | Money stored as text | every monetary column |
-- MAGIC | 5 | Timestamp stored as text | 5,152 rows dropped by a normal-looking filter |
-- MAGIC | 6 | JSON key absent, not null | 14 records |
-- MAGIC
-- MAGIC Every one of them is **mechanical**. A type is wrong, a value is missing, a row
-- MAGIC arrived twice. The data itself tells you the answer: there is no argument about
-- MAGIC whether `runtime_minutes` should be a number, and no judgment call about whether
-- MAGIC 900 duplicate rows should be 900 rows.
-- MAGIC
-- MAGIC Hold on to that word, *mechanical*. It is going to matter in about four minutes.
-- MAGIC
-- MAGIC Also notice what you have **not** done. You have not decided what any of this data
-- MAGIC *means*. Not once.
-- MAGIC
-- MAGIC → **02_let_the_ai_clean_it**
