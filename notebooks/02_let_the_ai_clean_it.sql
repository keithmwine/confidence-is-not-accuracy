-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 02 — Now let the AI do it
-- MAGIC
-- MAGIC You spent fifteen minutes finding five defects. Let's see how long the assistant
-- MAGIC takes to fix all of them.
-- MAGIC
-- MAGIC **Open the assistant** — the sparkle icon at the top right of this notebook, or
-- MAGIC `Cmd`/`Ctrl` + `I` inside a cell. In this workspace it is called **Genie Code**.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## The prompt
-- MAGIC
-- MAGIC Copy this in. It is nothing clever — it is just the list you built in notebook 01,
-- MAGIC written out in English.
-- MAGIC
-- MAGIC > Write SQL to create a table `workspace.media_lab.silver_viewing_sessions` from
-- MAGIC > `workspace.media_lab.bronze_playback_events`, fixing these problems:
-- MAGIC > `start_ts` is a string and should be a real timestamp; `ingest_date` is a string
-- MAGIC > and should be a date; `platform` is null on some rows and should be `'unknown'`
-- MAGIC > instead, keeping the row; the same `session_id` appears more than once because
-- MAGIC > the feed delivers at least once, so keep exactly one row per `session_id`. Cast
-- MAGIC > `household_id` and `content_id` to bigint and `watch_seconds` to int. Add a
-- MAGIC > column `event_date` holding the calendar date of `start_ts`.
-- MAGIC
-- MAGIC Then do the catalog too:
-- MAGIC
-- MAGIC > Write SQL to create `workspace.media_lab.silver_content` from
-- MAGIC > `workspace.media_lab.bronze_content`, casting every column to a sensible type.
-- MAGIC > It came from a CSV so all of them are currently strings.
-- MAGIC
-- MAGIC Two prompts, so you get two statements. Put each one in its own cell below and
-- MAGIC run them.

-- COMMAND ----------

-- Your generated SQL for silver_viewing_sessions goes here.


-- COMMAND ----------

-- Your generated SQL for silver_content goes here.


-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## The reference version
-- MAGIC
-- MAGIC Your SQL will not match this word for word, and it does not need to. Run this one
-- MAGIC anyway, so that everybody in the room is working from identical tables for the rest
-- MAGIC of the session.

-- COMMAND ----------

CREATE OR REPLACE TABLE workspace.media_lab.silver_viewing_sessions AS
WITH typed AS (
  SELECT
    session_id,
    CAST(household_id AS BIGINT)      AS household_id,
    CAST(content_id AS BIGINT)        AS content_id,
    device_id,
    CAST(start_ts AS TIMESTAMP)       AS start_ts,
    CAST(watch_seconds AS INT)        AS watch_seconds,
    -- Keep the row, label the gap. Dropping it would understate every total.
    COALESCE(platform, 'unknown')     AS platform,
    CAST(is_live AS BOOLEAN)          AS is_live,
    CAST(rebuffer_seconds AS DOUBLE)  AS rebuffer_seconds,
    CAST(startup_ms AS INT)           AS startup_ms,
    CAST(ingest_date AS DATE)         AS ingest_date,
    -- One row per session, deterministically chosen.
    ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY start_ts) AS dedupe_rank
  FROM workspace.media_lab.bronze_playback_events
)
SELECT
  session_id, household_id, content_id, device_id,
  start_ts,
  DATE(start_ts) AS event_date,
  watch_seconds, platform, is_live, rebuffer_seconds, startup_ms, ingest_date
FROM typed
WHERE dedupe_rank = 1;

-- COMMAND ----------

CREATE OR REPLACE TABLE workspace.media_lab.silver_content AS
SELECT
  CAST(content_id AS BIGINT)      AS content_id,
  title,
  series_title,
  network,
  content_type,
  genre,
  CAST(season_number AS INT)      AS season_number,
  CAST(episode_number AS INT)     AS episode_number,
  CAST(runtime_minutes AS INT)    AS runtime_minutes,
  CAST(premiere_date AS DATE)     AS premiere_date,
  CAST(is_original AS BOOLEAN)    AS is_original
FROM workspace.media_lab.bronze_content;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Did it work?
-- MAGIC
-- MAGIC Never take a cleanup on trust — yours or an AI's. Re-run the same checks that
-- MAGIC found the bugs in the first place.

-- COMMAND ----------

SELECT
  COUNT(*)                            AS rows,
  COUNT(DISTINCT session_id)          AS distinct_sessions,
  COUNT_IF(start_ts IS NULL)          AS null_timestamps,
  COUNT_IF(platform IS NULL)          AS null_platform,
  COUNT_IF(platform = 'unknown')      AS labelled_unknown,
  typeof(ANY_VALUE(start_ts))         AS start_ts_type,
  typeof(ANY_VALUE(event_date))       AS event_date_type
FROM workspace.media_lab.silver_viewing_sessions;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Expected: **300,000 rows and 300,000 distinct sessions** (the 900 duplicates are
-- MAGIC gone), **zero null timestamps**, **zero null platforms** with **1,587 labelled
-- MAGIC `unknown`** (the rows kept, the gap still visible), and real `timestamp` and
-- MAGIC `date` types.
-- MAGIC
-- MAGIC 1,587, not the 1,590 you counted in notebook 01, because three of those rows were
-- MAGIC among the duplicates. Both fixes are correct and they overlap.
-- MAGIC
-- MAGIC And the two queries that were confidently wrong in notebook 01. Now that the
-- MAGIC types are real, the plain, obvious way to write them is also the correct way —
-- MAGIC which is the entire reason this layer exists.

-- COMMAND ----------

-- 155,752 in notebook 01 needed an explicit CAST to get right. Now it just works — and
-- returns 155,294, because 458 of the 900 duplicates you removed were August rows.
SELECT COUNT(*) AS august_sessions
FROM workspace.media_lab.silver_viewing_sessions
WHERE start_ts >= TIMESTAMP'2026-08-01'
  AND start_ts <  TIMESTAMP'2026-09-01';

-- COMMAND ----------

-- 94 and 115 in notebook 01. Should now be 180 and 30.
SELECT
  MAX(runtime_minutes) AS longest_runtime,
  MIN(runtime_minutes) AS shortest_runtime
FROM workspace.media_lab.silver_content;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## So what just happened
-- MAGIC
-- MAGIC The assistant did in about twenty seconds what took you fifteen minutes, and it
-- MAGIC got it right.
-- MAGIC
-- MAGIC It got it right because of the word from the end of notebook 01: those problems
-- MAGIC were **mechanical**. The correct answer was determined by the data itself. A
-- MAGIC timestamp column should hold timestamps. 900 duplicate rows should be 900 rows.
-- MAGIC There is no judgment in any of it, no context you had to go and ask somebody for.
-- MAGIC That is exactly the kind of work a language model is genuinely, reliably good at —
-- MAGIC and it is going to keep getting faster and cheaper at it.
-- MAGIC
-- MAGIC So be honest about the implication. If your value was *knowing that CSVs need
-- MAGIC casting*, that value is dropping fast.
-- MAGIC
-- MAGIC Which brings us to the actual question of this workshop. Your tables are now
-- MAGIC clean, correctly typed, deduplicated, and complete.
-- MAGIC
-- MAGIC **Can you trust the answers you get from them?**
-- MAGIC
-- MAGIC → **03_ask_a_question**
