# Instructor runbook

**⚠️ Spoilers.** This document gives away every planted mistake. If you are a workshop
participant, close it and open `notebooks/01_find_the_bugs` instead.

90 minutes. URI CS Connect Day, Friday September 18 2026, 2:00–3:30pm, Bliss Hall 290,
capacity 32.

---

## The one sentence

If you get one idea across, make it this:

> The wrong answer showed up **after** the data was clean. Cleaning was never the hard
> part, and it is the part that just got automated.

Everything else in the session is scaffolding for that.

---

## Before you walk in

**The day before**

- [ ] Run the full path yourself in a *fresh* Free Edition account, the way a student
      will: sign up, clone the Git folder, run `00_setup`, work through all four
      notebooks. Roughly 25 minutes and it is the only real test.
- [ ] Build the Genie agent yourself and ask the question. Note what SQL it writes today
      (it varies), so you are not surprised on stage.
- [ ] Confirm the repo is public: open the clone URL in a private browser window.
- [ ] Have the numbers below on a second screen or on paper.

**In the room, before you start**

- [ ] Repo URL and the signup URL on a slide, large, left up for the whole session.
      Students will be typing them at different times.
- [ ] Warn them the first query of the session takes ~30 seconds — the Free Edition SQL
      warehouse is asleep and has to wake up. Otherwise a third of the room thinks they
      broke it.
- [ ] Ask who has used SQL before. It changes how much you narrate notebook 01.

---

## Timing

| Clock | Minutes | Segment |
|---|---|---|
| 2:00 | 12 | Setup, running in parallel with the welcome |
| 2:12 | 8 | Frame the question |
| 2:20 | 15 | `01_find_the_bugs` |
| 2:35 | 10 | `02_let_the_ai_clean_it` |
| 2:45 | 20 | `03_ask_a_question` — the turn |
| 3:05 | 20 | `04_encode_what_you_know` |
| 3:25 | 5 | Close |

**If you are running late**, cut in this order — these are ranked so the arc survives:

1. The four-definition cell in `03` (keep the two-ranking comparison; it carries the point)
2. Level 1 (catalog comments) in `04` — mention it, don't run it
3. The `hours_of_playback` nuance in `03`
4. The "Your turn" ad-sales exercise in `04` — tell them it's homework

**Never cut**: the naive ranking in `03`, the `pct_that_stayed` column, and the metric
view in `04`. That is the workshop.

---

## 2:00 — Setup (12 min)

Put both URLs up and start talking while they work. Do not wait for silence; do not go
notebook by notebook as a group. People will finish between minute 4 and minute 11 and
that is fine.

Walk the room. The three things that actually go wrong:

| Symptom | Fix |
|---|---|
| Email verification code hasn't arrived | Have them use Sign in with Google instead. Do not wait on email. |
| "Create → Git folder" not visible | They're in a different part of the workspace. Sidebar → **Workspace** → their own user folder → **Create**. |
| `00_setup` fails on the data folder | They opened the notebook from somewhere other than the Git folder. Re-open it from Workspace → the cloned folder → `notebooks`. |

Anyone still stuck at minute 10: **pair them with a neighbour**. Two people at one laptop
works completely fine for this material and is much better than one person watching a
spinner for 90 minutes.

`00_setup` takes about 70 seconds and prints `READY` with six row counts. If a count
disagrees it raises instead of continuing — that is deliberate, every number in this
runbook is keyed to those counts.

---

## 2:12 — Frame the question (8 min)

No slides needed. Three beats:

1. **The claim.** A model's confidence is not correlated with its accuracy. A wrong
   answer is fluent, fast, well-formatted and unhedged, exactly like a right one. You
   cannot tell them apart by looking.
2. **The usual answer, and why it's incomplete.** "Prompt better" and "clean your data"
   are both real, and neither is sufficient — you're going to watch a wrong answer come
   out of clean data and a perfectly reasonable question.
3. **What this session is.** Not a Databricks tutorial. Ninety minutes on where the
   judgment lives once the tool is good at the typing, and which of your skills that
   makes *more* valuable rather than less.

Worth saying out loud, because this audience is anxious about it: the AI is going to be
genuinely, impressively good in about twenty minutes. Don't undersell it. The point is
sharper when the tool is strong.

---

## 2:20 — `01_find_the_bugs` (15 min)

Let them run it. Circulate rather than narrate. Come together for bugs 3 and 5.

**Numbers to have ready** (all verified against the committed data):

| Bug | Query result |
|---|---|
| 1. Duplicates | 300,900 landed / 300,000 distinct / **900 duplicates** |
| 2. Missing platform | **1,590** rows with no platform (1,587 distinct sessions) |
| 3. Text numbers | `MAX` = **94**, `MIN` = **115** as text; real answers **180** and **30** |
| 4. Text money | highest CPM **$9.99** as text, **$67.74** as a number |
| 5. String timestamp | 150,600 the easy way vs 155,752 real — **5,152 silently dropped** |
| 6. Absent JSON key | **14** of 400 records |

**Bug 3 is the one to stop on.** The minimum is larger than the maximum. Ask the room why
before you explain — someone will get there. Then make the general point: it did not
error, it did not return null, it returned two confident specific numbers that are both
wrong.

**Bug 5 is the one to linger on.** 150,600 is a completely believable number. It is off
by 3.3% because a normal-looking `BETWEEN` on a text column drops all of August 31st. Ask:
*how would you ever have caught this if you hadn't written the second version?*

End the segment on the last markdown cell's two words: these bugs are all **mechanical**,
and you have not decided what any of this data *means*.

---

## 2:35 — `02_let_the_ai_clean_it` (10 min)

They open the assistant (Genie Code) and paste the prompt from the notebook. Give it a
minute, then ask two or three people to read out what they got. It will differ in style
and agree in substance.

**Do this on your own screen while they work:** paste the prompt, and let the room watch
the SQL appear. Then say the timing out loud — twenty seconds against their fifteen
minutes.

Then the reference cell, so everyone is on identical tables. Verification should show
**300,000 rows, 300,000 distinct, 0 null timestamps, 0 null platforms, 1,587 labelled
`unknown`**, and real `timestamp` / `date` types.

Two numbers shift between notebooks because dedupe and the other defects overlap, and both
are worth having ready rather than explaining on the spot:

- **1,587 labelled `unknown`, not the 1,590** from notebook 01 — three of the null-platform
  rows were also duplicates.
- **155,294 August sessions, not the 155,752** from notebook 01 — 458 of the 900 duplicates
  were August rows.

**Land this properly, without flinching:**

- It got it right. Not approximately — correctly, including keeping the null-platform rows
  instead of dropping them.
- It got it right *because the problems were mechanical*. The data itself determined the
  answer. No context, no judgment, nobody to go ask.
- So be honest about what that means: if your value was knowing that CSVs need casting,
  that value is falling.

Then the hinge question, and let it sit for a second before moving on:

> Your data is now clean, typed, deduplicated and complete. Can you trust the answers?

---

## 2:45 — `03_ask_a_question` (20 min) — the turn

This is the segment that matters. Budget generously; it is where the room turns.

**Agent build (~5 min).** Sidebar → **Genie** → **Genie Agents** → **New** → add exactly
`silver_viewing_sessions` and `silver_content` → **Create**. Some workspaces still say
*Genie spaces*; same thing.

Everyone has their own workspace, so everyone builds their own agent — no sharing problem
to manage. Circulate.

**The question**, word for word:

> Which titles had the most views on Tidewater?

**Make them write down the top three before you say anything.** Committing to an answer
in writing is what makes the reveal land instead of washing over them.

**Then: "click Show generated code."** Read the SQL as a room. Ask: does anyone see a
problem with this query? They will not, because there isn't one. It is correct SQL over
clean data.

### What Genie will say

Usually `COUNT(*) ... GROUP BY title`, giving:

| Rank | Title | "views" |
|---|---|---|
| 1 | Night Circuit | 10,705 |
| 2 | Night Harbor S04E07 | 10,399 |
| 3 | Night Harbor S01E09 | 9,858 |

**If it counted something else** — distinct households, or `SUM(watch_seconds)` — do not
treat that as a failure. It is a better opening than the one you planned. Say:

> Three of you got three different answers to the same question, and every one of the
> queries is valid. So which is right? Nothing in any of those outputs tells you it made
> a choice at all.

Then run the notebook's four-definition cell, which shows all of them side by side, and
carry on exactly as scripted.

### The pivot

Ask the question and *wait*:

> What is a view?

Let it be uncomfortable. Somebody will say "well, how long do you have to watch?" — that
is the moment. Then give them the company's rule: **a session of at least 30 seconds.
Anything shorter is channel surfing, and advertisers are not billed for it.**

Emphasise that this is not discoverable from the data. It is not a fact about the rows.
It's a decision the business made years ago and wrote down somewhere nobody in this room
has read.

### The reveal

The `pct_that_stayed` column does the work:

| Title | Started | Lasted 30s | Stayed |
|---|---|---|---|
| Night Circuit | 10,705 | 2,560 | **23.9%** |
| Night Harbor S04E07 | 10,399 | 2,565 | **24.7%** |
| Night Harbor S01E09 | 9,858 | 2,321 | **23.5%** |
| Tenth Alibi S04E18 | 7,839 | 6,989 | **89.2%** |
| Quiet Corridor S01E08 | 4,724 | 4,342 | **91.9%** |

Then the corrected ranking. The numbers to say out loud:

- **Genie's #1, `Night Circuit`, is really #11 of 32 titles.** Its two stablemates are
  #10 and #14.
- **The real #1 is `Tenth Alibi S04E18`** — it was sitting at #4, where nobody looked.
- Those three aren't hits. They're heavily promoted titles people sample and abandon.
  They win a `COUNT(*)` *because* nobody stays.

**The callback.** Have them scroll back to the very first cell they ran in notebook 01 —
the plain `SELECT * LIMIT 20`. There is a 9-second session and a 3-second session sitting
right there in the `watch_seconds` column. It was on their screen in the first thirty
seconds of the workshop and nobody said a word, because nobody had a reason to care yet.
Which is the whole problem: you cannot spot a missing definition by looking harder at the
data.

**The nuance, if you have time.** By `hours_of_playback`, `Night Circuit` genuinely *is*
first — it's a three-hour live event. So there was never one true answer to "most views."
There were several defensible ones, and the model picked one silently. Choosing which one
the business means, and making that choice impossible to get wrong, is the job.

---

## 3:05 — `04_encode_what_you_know` (20 min)

Three levels, and the escalation is the point.

**Level 1 — the catalog comment.** Run it, then immediately undercut it: a comment is a
sign, not a fence. The next person to write `COUNT(*)` gets the wrong answer just as fast.

**Level 2 — the metric view.** This is the intellectual centre of the session. Slow down.

Read the YAML with them. The rule appears **once**, inside `qualified_views`. Point out
that `sessions_started` is also there, deliberately, under a name nobody can mistake for
a view count. Then run the query: **`Tenth Alibi S04E18`, 6,989 qualified views, 89.2%**
— the same answer as the hand-written query, but now nobody has to know the rule to get
it right.

**Level 3 — the agent.** Add the instruction, add the metric view as a dataset, re-ask
the identical question.

If it is *still* wrong — and it might be — that is the best possible outcome, because it
sets up the strongest line in the session:

> The reliable way to stop getting a wrong answer is not to ask more nicely. It's to
> remove the path to the wrong answer.

Then have them delete the two silver tables from the agent's datasets, leaving only the
metric view, and ask again. A metric view with no raw table behind it has no `COUNT(*)`
to get wrong.

**Then the closing table**, and say the four rows out loud: same model, same prompt, same
data, different answer. What changed is that somebody wrote down what they knew.

---

## 3:25 — Close (5 min)

Three things, briefly:

1. **Fluency is not accuracy.** Not for the model, and not for the SQL they wrote
   themselves in notebook 01. `MIN` bigger than `MAX` looked perfectly normal too.
2. **What appreciates.** Knowing what the business means. Modelling data so the right
   answer is the easy one. Writing down what you know. And looking at a number and saying
   *that can't be right* — then proving it. None of those got easier when the model got
   better at SQL; all of them got more valuable, because the model now executes flawlessly
   on whatever definition you hand it, including a wrong one, very fast.
3. **They keep everything.** The account is free and doesn't expire. The tables, the
   metric view and the agent are all still there tomorrow. The repo has an unfinished
   second exercise in it (ad sales, `fill_status`) and `generator/generate.py` shows
   exactly how every mistake was planted.

Leave the repo URL up while they pack.

---

## Risks, ranked by likelihood

| Risk | Mitigation |
|---|---|
| Genie writes a different query than expected | Scripted above — it's a better opening than the planned one. |
| Room-wide wifi trouble | Everything but the two Genie segments is a notebook. Notebook 03's cells reproduce the wrong answer and the correction with plain SQL, so **the whole arc survives with no Genie at all** — you drive it on your screen and they read along. |
| Genie Code (the assistant) unavailable or out of quota for someone | The reference SQL is right there in notebook 02. Nobody is blocked. |
| Someone can't get an account | Pair them up. Immediately, not at minute 25. |
| Behind schedule | Cut list is above. |
| Warehouse cold start read as a broken notebook | Warn them at the start. |
| A student reads `generator/` and spoils trap 1 | Low, and honestly fine — anyone curious enough to read the generator mid-session has already got the lesson. |

---

## Numbers appendix

Everything below is reproducible: `uv run --with numpy,pandas,pyarrow generator/generate.py`
regenerates byte-identical files (seed 42), and the generator asserts the traps still hold.

**Row counts after `00_setup`**

| Table | Rows |
|---|---|
| `bronze_content` | 88 |
| `bronze_households` | 3,000 |
| `bronze_advertisers` | 40 |
| `bronze_playback_events` | 300,900 |
| `bronze_ad_impressions` | 180,000 |
| `bronze_viewer_feedback` | 400 |

**Planted titles (trap 1), all on Tidewater**

`Night Circuit` · `Night Harbor S04E07` · `Night Harbor S01E09`

Volume 1.9–2.1× the best normal title; 76% of their sessions are 3–29 second surfs.
Guaranteed arithmetically, not by luck — the generator asserts both margins (raw 1.90×,
qualified 1.77×) before it writes a file.

**Rank movement, post-dedupe silver**

| Title | By `COUNT(*)` | By qualified views | Stayed |
|---|---|---|---|
| Night Circuit | 1 | **11** of 32 | 23.9% |
| Night Harbor S04E07 | 2 | **10** | 24.7% |
| Night Harbor S01E09 | 3 | **14** | 23.5% |
| Tenth Alibi S04E18 | 4 | **1** | 89.2% |

**Whole dataset:** 21.9% of all sessions are under 30 seconds (66,032 of 300,900).

**Trap 2 (the "your turn" exercise), average CPM**

| Network | Every slot | Filled only | Filled % |
|---|---|---|---|
| Meridian News | $20.99 | **$29.85** | 70.3% |
| Tidewater | $12.59 | **$17.99** | 70.0% |
| Nova | $9.08 | **$12.94** | 70.1% |

**Trap 3, not used in the 90-minute session.** The broadcast day runs 06:00–06:00, so
overnight sessions belong to the previous broadcast date. 11.2% of sessions start before
06:00. It is in the data and it is real, but with no day-of-week seasonality in the
generator the corrected day-of-week ranking barely moves (~1%), so it does not survive
contact with a projector. Left documented rather than taught.
