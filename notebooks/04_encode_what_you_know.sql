-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 04 — Encode what you know
-- MAGIC
-- MAGIC The model is not going to figure out the 30-second rule. It cannot. The rule is not
-- MAGIC in the data, and no amount of prompt engineering will conjure a fact that nobody
-- MAGIC wrote down.
-- MAGIC
-- MAGIC So write it down. Three levels, weakest to strongest.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Level 1 — say it in the catalog
-- MAGIC
-- MAGIC A column comment is documentation that travels with the data instead of rotting in
-- MAGIC a wiki. Humans see it when they browse the table. Genie reads it as context.

-- COMMAND ----------

ALTER TABLE workspace.media_lab.silver_viewing_sessions
ALTER COLUMN watch_seconds
COMMENT 'Seconds of content played in this session. A session of at least 30 seconds is a qualified view; anything shorter is channel surfing and is not counted as a view or billed to advertisers.';

-- COMMAND ----------

COMMENT ON TABLE workspace.media_lab.silver_viewing_sessions IS
'One row per playback session, deduplicated. Includes very short sessions from channel surfing, so COUNT(*) is a count of playback starts and NOT a count of views. Use the viewing metric view for view counts.';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC That is a real improvement and it is not enough.
-- MAGIC
-- MAGIC A comment is a *sign*, not a *fence*. The next person to write
-- MAGIC `SELECT COUNT(*) ... GROUP BY title` gets the wrong answer just as fast as before,
-- MAGIC and so does the next AI, if either of them doesn't happen to read it.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Level 2 — make the definition a thing you can query
-- MAGIC
-- MAGIC A **metric view** turns the business rule into an object in the catalog. The
-- MAGIC dimensions are what you are allowed to slice by; the measures are the *only*
-- MAGIC arithmetic anyone gets, and the 30-second rule is welded inside them.
-- MAGIC
-- MAGIC Read `qualified_views` and `sessions_started` below. Both are available, and they
-- MAGIC are named so that nobody can confuse one for the other by accident.

-- COMMAND ----------

CREATE OR REPLACE VIEW workspace.media_lab.viewing
WITH METRICS
LANGUAGE YAML
COMMENT 'The company definition of viewing. A qualified view is a session of at least 30 seconds; anything shorter is channel surfing and is not a view.'
AS $$
version: 0.1
source: workspace.media_lab.silver_viewing_sessions
joins:
  - name: content
    source: workspace.media_lab.silver_content
    on: source.content_id = content.content_id
dimensions:
  - name: network
    expr: content.network
  - name: title
    expr: content.title
  - name: series
    expr: content.series_title
  - name: genre
    expr: content.genre
  - name: platform
    expr: source.platform
  - name: event_date
    expr: source.event_date
measures:
  # The rule lives here, once, where nobody has to remember it.
  - name: qualified_views
    expr: COUNT(CASE WHEN source.watch_seconds >= 30 THEN 1 END)
  - name: sessions_started
    expr: COUNT(1)
  - name: qualification_rate
    expr: 100.0 * COUNT(CASE WHEN source.watch_seconds >= 30 THEN 1 END) / COUNT(1)
  - name: households_reached
    expr: COUNT(DISTINCT CASE WHEN source.watch_seconds >= 30 THEN source.household_id END)
  - name: hours_viewed
    expr: SUM(CASE WHEN source.watch_seconds >= 30 THEN source.watch_seconds END) / 3600.0
$$;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Now ask the original question against the metric view. `MEASURE()` is how you read a
-- MAGIC measure — it is the syntax that tells you you are getting the company's definition
-- MAGIC rather than your own guess.

-- COMMAND ----------

SELECT
  title,
  MEASURE(qualified_views)                AS qualified_views,
  MEASURE(sessions_started)               AS sessions_started,
  ROUND(MEASURE(qualification_rate), 1)   AS pct_that_stayed
FROM workspace.media_lab.viewing
WHERE network = 'Tidewater'
GROUP BY title
ORDER BY qualified_views DESC
LIMIT 5;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Same answer as the hand-written query in notebook 03 — `Tenth Alibi S04E18` on top
-- MAGIC with 6,989 qualified views and 89.2% retention.
-- MAGIC
-- MAGIC The difference is that nobody has to know the rule to get it right anymore. It is
-- MAGIC not in a query somebody has to remember to copy. It is in the catalog, versioned,
-- MAGIC governed, and identical for every person and every tool that asks.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Level 3 — tell the agent, then take away the wrong answer
-- MAGIC
-- MAGIC Back to your Genie Agent. Two changes.
-- MAGIC
-- MAGIC **First, add the instruction.** Open your agent → **Configure** → **Instructions**,
-- MAGIC and paste this:
-- MAGIC
-- MAGIC > A "view" always means a qualified view: a viewing session with `watch_seconds` of
-- MAGIC > 30 or more. Sessions under 30 seconds are channel surfing and must never be
-- MAGIC > counted as views. For any question about views, reach, or hours watched, use the
-- MAGIC > `workspace.media_lab.viewing` metric view rather than counting rows in
-- MAGIC > `silver_viewing_sessions`.
-- MAGIC
-- MAGIC **Second, add the metric view as a dataset:** **Configure** → **Data**, and add
-- MAGIC `workspace.media_lab.viewing`.
-- MAGIC
-- MAGIC Now ask the same question again, word for word:
-- MAGIC
-- MAGIC > **Which titles had the most views on Tidewater?**

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### If it is still wrong
-- MAGIC
-- MAGIC It might be. An instruction is a strong hint, not a guarantee — the agent can still
-- MAGIC reach for `silver_viewing_sessions` and count rows.
-- MAGIC
-- MAGIC So stop hinting. In **Configure** → **Data**, *remove* `silver_viewing_sessions`
-- MAGIC and `silver_content`, leaving only the `viewing` metric view. Ask again.
-- MAGIC
-- MAGIC This is the most useful idea in the workshop, so it is worth saying plainly:
-- MAGIC
-- MAGIC > The reliable way to stop getting a wrong answer is not to ask more nicely. It is
-- MAGIC > to remove the path to the wrong answer.
-- MAGIC
-- MAGIC A metric view with no raw table behind it cannot be miscounted. There is no
-- MAGIC `COUNT(*)` available to get wrong.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## What actually changed
-- MAGIC
-- MAGIC Compare where you started to where you are.
-- MAGIC
-- MAGIC | | Before | After |
-- MAGIC |---|---|---|
-- MAGIC | The model | the same model | the same model |
-- MAGIC | The prompt | "most views on Tidewater" | the same words |
-- MAGIC | The data | clean, typed, deduplicated | unchanged |
-- MAGIC | The answer | `Night Circuit`, really #11 of 32 | `Tenth Alibi S04E18`, correct |
-- MAGIC
-- MAGIC The model did not get smarter. The prompt did not get more clever. The data was
-- MAGIC already clean before the wrong answer showed up.
-- MAGIC
-- MAGIC What changed is that **somebody wrote down what they knew** — and put it where the
-- MAGIC machine and the next engineer would both trip over it, instead of in their own head.
-- MAGIC
-- MAGIC That somebody needed two things a model cannot supply: they had to *know* the
-- MAGIC business rule, and they had to know how to model data so a rule can be enforced
-- MAGIC instead of merely suggested. Notice that neither of those got easier when the AI got
-- MAGIC better at SQL. They got **more valuable**, because the AI now executes flawlessly on
-- MAGIC whatever definition it is handed — including a wrong one, at enormous speed.
-- MAGIC
-- MAGIC And there is one more job, which is the one you just did five times in this
-- MAGIC workshop: somebody has to **look at the answer and ask whether it makes sense**.
-- MAGIC A title where 76% of people leave in under thirty seconds is not the network's
-- MAGIC biggest hit, and the only reason anyone knows that is that a human looked at it.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Your turn
-- MAGIC
-- MAGIC You now have the whole pattern. Here is a second wrong answer hiding in the same
-- MAGIC dataset — same shape, different column. Take it as far as you like, in the room or
-- MAGIC on the train home.
-- MAGIC
-- MAGIC **The question:** *What is our average CPM on Meridian News?* CPM is what an
-- MAGIC advertiser pays per thousand impressions, and it is the number the sales team quotes
-- MAGIC on a rate card.
-- MAGIC
-- MAGIC Run the cell below.

-- COMMAND ----------

SELECT
  c.network,
  ROUND(AVG(CAST(i.cpm AS DOUBLE)), 2)                                        AS avg_cpm_every_slot,
  ROUND(AVG(CASE WHEN i.fill_status = 'filled'
                 THEN CAST(i.cpm AS DOUBLE) END), 2)                          AS avg_cpm_filled_only,
  ROUND(100.0 * COUNT_IF(i.fill_status = 'filled') / COUNT(*), 1)             AS pct_of_slots_filled
FROM workspace.media_lab.bronze_ad_impressions i
JOIN workspace.media_lab.silver_content c USING (content_id)
GROUP BY c.network
ORDER BY avg_cpm_filled_only DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC `$20.99` versus `$29.85` on Meridian News. Quote the first number to an advertiser
-- MAGIC and you have just underpriced your best inventory by 30%.
-- MAGIC
-- MAGIC The reason is the same as before. About 30% of ad slots never sell — they run a
-- MAGIC promo or nothing at all, at a CPM of zero. Averaging those zeros in with real sales
-- MAGIC answers a question nobody asked. The `fill_status` column has been sitting there the
-- MAGIC whole time saying `filled`, `unfilled`, `house`. What is *not* anywhere in the data
-- MAGIC is the sentence **"only filled slots earn money."**
-- MAGIC
-- MAGIC Your exercise, in the order you did it above:
-- MAGIC
-- MAGIC 1. Build `silver_ad_impressions` from the bronze table, casting `cpm` and
-- MAGIC    `revenue_usd` to real numbers. Ask the assistant — it is a mechanical job.
-- MAGIC 2. Comment `fill_status` so the next person knows what it controls.
-- MAGIC 3. Build a second metric view, `ad_inventory`, with measures like `filled_slots`,
-- MAGIC    `revenue`, `effective_cpm` and `fill_rate` — each one with the
-- MAGIC    `fill_status = 'filled'` rule welded in where it belongs.
-- MAGIC 4. Add it to your agent and ask about CPM, revenue and fill rate. Try to get a
-- MAGIC    wrong answer out of it. That is the test of whether you encoded the rule or just
-- MAGIC    described it.
-- MAGIC
-- MAGIC ---
-- MAGIC
-- MAGIC ## Keep this
-- MAGIC
-- MAGIC Your Databricks account is free and it does not expire. Everything you built is
-- MAGIC still here tomorrow: the volume, the bronze and silver tables, the metric view, the
-- MAGIC agent. So is this repo, including `generator/generate.py`, which shows you exactly
-- MAGIC where every mistake in the data was planted and why.
-- MAGIC
-- MAGIC Two things worth taking with you:
-- MAGIC
-- MAGIC **Fluency is not accuracy.** You cannot tell a right answer from a wrong one by how
-- MAGIC good it looks, how fast it arrived, or how sure it sounds. That was true of the SQL
-- MAGIC you wrote yourself, and it is true of everything a model will ever hand you.
-- MAGIC
-- MAGIC **The skills that appreciate are the ones a model cannot get from your data.**
-- MAGIC Knowing what the business actually means. Modelling data so the right answer is the
-- MAGIC easy one and the wrong one is unavailable. Writing down what you know. And looking
-- MAGIC at a number and saying *that can't be right* — then proving it.
