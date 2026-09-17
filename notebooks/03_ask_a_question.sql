-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 03 — Ask a question
-- MAGIC
-- MAGIC Your data is clean. Now hand it to an AI and ask it something.
-- MAGIC
-- MAGIC This notebook has a step you do in the UI first, then come back here.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Build the agent (about three minutes)
-- MAGIC
-- MAGIC 1. In the left sidebar, click **Genie** → **Genie Agents**. (Some workspaces still
-- MAGIC    label these *Genie spaces* — same thing.)
-- MAGIC 2. Click **New**.
-- MAGIC 3. Add exactly two tables:
-- MAGIC    - `workspace.media_lab.silver_viewing_sessions`
-- MAGIC    - `workspace.media_lab.silver_content`
-- MAGIC 4. Click **Create**. Name it whatever you like.
-- MAGIC
-- MAGIC That is the entire setup. Two clean tables and a text box. This is roughly what a
-- MAGIC company means when it says it has "AI on its data."

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Ask it this
-- MAGIC
-- MAGIC > **Which titles had the most views on Tidewater?**
-- MAGIC
-- MAGIC Then do three things, in this order, before you read any further:
-- MAGIC
-- MAGIC 1. **Write down the top three titles it gives you.** On paper, or in the cell below.
-- MAGIC 2. Click **Show generated code** (or the SQL toggle) and *read the query it wrote*.
-- MAGIC 3. Decide whether you believe it. Fluent, formatted, instant, no warnings, no
-- MAGIC    hedging. Would you forward this to your boss?
-- MAGIC
-- MAGIC Most of the time the query it writes is some version of
-- MAGIC `COUNT(*) ... GROUP BY title ORDER BY ... DESC`. If yours counted something else —
-- MAGIC distinct households, or total watch time — that is not a mistake on your part, and
-- MAGIC it is about to become the most interesting thing in the room. Keep it.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ```
-- MAGIC Genie's top three:
-- MAGIC   1.
-- MAGIC   2.
-- MAGIC   3.
-- MAGIC
-- MAGIC The SQL it wrote counted:
-- MAGIC ```

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## The query it probably wrote
-- MAGIC
-- MAGIC Run it. It is correct SQL over correct data, and it will agree with Genie.

-- COMMAND ----------

SELECT
  c.title,
  COUNT(*) AS views
FROM workspace.media_lab.silver_viewing_sessions s
JOIN workspace.media_lab.silver_content c USING (content_id)
WHERE c.network = 'Tidewater'
GROUP BY c.title
ORDER BY views DESC
LIMIT 5;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## One question
-- MAGIC
-- MAGIC Before the next cell, answer this out loud:
-- MAGIC
-- MAGIC ### What is a "view"?
-- MAGIC
-- MAGIC You have been saying the word this whole time. Genie used it in an answer. Nobody
-- MAGIC has defined it.
-- MAGIC
-- MAGIC You start a stream, watch four seconds, decide it isn't for you, and flip to
-- MAGIC something else. Was that a view?
-- MAGIC
-- MAGIC There is no way to answer that from the data. It is not a fact about the rows. It
-- MAGIC is a decision the business made — and at this company, like at most real ones, it
-- MAGIC was made years ago and written down somewhere you have not read: **a view is a
-- MAGIC session that lasted at least 30 seconds.** Anything shorter is channel surfing.
-- MAGIC It does not count, and advertisers are not billed for it.
-- MAGIC
-- MAGIC Now run the same question four ways.

-- COMMAND ----------

SELECT
  c.title,
  COUNT(*)                                                        AS sessions_started,
  COUNT_IF(s.watch_seconds >= 30)                                 AS lasted_30_seconds,
  ROUND(100.0 * COUNT_IF(s.watch_seconds >= 30) / COUNT(*), 1)    AS pct_that_stayed,
  COUNT(DISTINCT CASE WHEN s.watch_seconds >= 30
                      THEN s.household_id END)                    AS households_reached,
  ROUND(SUM(s.watch_seconds) / 3600.0, 0)                         AS hours_of_playback
FROM workspace.media_lab.silver_viewing_sessions s
JOIN workspace.media_lab.silver_content c USING (content_id)
WHERE c.network = 'Tidewater'
GROUP BY c.title
ORDER BY sessions_started DESC
LIMIT 8;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Look at the `pct_that_stayed` column.
-- MAGIC
-- MAGIC The three titles Genie put at the top keep about **24%** of the people who start
-- MAGIC them. Everything below them keeps **85 to 92%**.
-- MAGIC
-- MAGIC Those three are not hits. They are heavily promoted titles that a lot of people
-- MAGIC sample for a few seconds and abandon. They win a `COUNT(*)` precisely *because*
-- MAGIC nobody stays — you cannot start something twice in one sitting unless you keep
-- MAGIC leaving.
-- MAGIC
-- MAGIC Now rank by the company's actual definition.

-- COMMAND ----------

SELECT
  c.title,
  COUNT(*)                                                      AS sessions_started,
  COUNT_IF(s.watch_seconds >= 30)                               AS qualified_views,
  ROUND(100.0 * COUNT_IF(s.watch_seconds >= 30) / COUNT(*), 1)  AS pct_that_stayed
FROM workspace.media_lab.silver_viewing_sessions s
JOIN workspace.media_lab.silver_content c USING (content_id)
WHERE c.network = 'Tidewater'
GROUP BY c.title
ORDER BY qualified_views DESC
LIMIT 8;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## A completely different answer
-- MAGIC
-- MAGIC Genie's #1, `Night Circuit`, is really **#11 out of 32 titles**. Its two
-- MAGIC stablemates land at #10 and #14. Not one of the three belongs anywhere near a
-- MAGIC top-five list, and the real #1 — `Tenth Alibi S04E18` — was sitting at #4 where
-- MAGIC nobody was looking.
-- MAGIC
-- MAGIC Sit with what that would have cost. This is the list that decides which titles get
-- MAGIC renewed, which get the promo budget, and which advertisers are told about. Getting
-- MAGIC it backwards is a real business decision made on a real wrong number.
-- MAGIC
-- MAGIC And notice how the failure arrived:
-- MAGIC
-- MAGIC - The **data was clean.** You cleaned it yourself, one notebook ago, and verified it.
-- MAGIC - The **SQL was valid.** Anyone would have written the same query.
-- MAGIC - The **answer was fluent, fast, formatted and specific.** It looked like every
-- MAGIC   correct answer you have ever seen.
-- MAGIC - **Nothing** in the output was flagged, hedged, or marked uncertain.
-- MAGIC
-- MAGIC Confidence told you nothing. It never does. A wrong answer arrives in exactly the
-- MAGIC same tone as a right one, and no amount of cleverness in how you phrase the
-- MAGIC question fixes it, because the model was never missing *words* — it was missing a
-- MAGIC **fact about the business** that existed nowhere in the data it was given.
-- MAGIC
-- MAGIC One more thing, and it is the part most people miss. Look at `hours_of_playback` in
-- MAGIC the previous cell: by *that* measure `Night Circuit` genuinely is first, because it
-- MAGIC is a three-hour live event. So there was never one true answer to "the most views"
-- MAGIC — there were several defensible ones, and the model picked one silently and told
-- MAGIC you none of that. Choosing which definition the business actually means, and then
-- MAGIC making that choice impossible to get wrong, is the job.
-- MAGIC
-- MAGIC So let's do that job.
-- MAGIC
-- MAGIC → **04_encode_what_you_know**
