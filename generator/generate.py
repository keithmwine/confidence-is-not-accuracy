#!/usr/bin/env python3
"""Build the messy streaming-media dataset for the workshop.

SPOILER WARNING. This file is the answer key. It shows exactly where every
mistake in the data was planted and why. If you want the workshop's surprises
intact, work through the notebooks first and come back here afterward.

Runs locally in a few seconds, no Spark and no cloud account:

    uv run --with numpy,pandas,pyarrow generator/generate.py

Output lands in ../data and is committed to the repo, so every student in the
room gets byte-identical files and every number in the runbook holds. Nothing
here is random at run time -- one seed, fixed operation order.

Three source formats on purpose. Real landing zones are never uniform, and
"everything in the CSV is a string" is one of the bugs students are meant to
find.

    content.csv, households.csv, advertisers.csv   operational system exports
    playback_events.parquet                        high-volume event feed
    ad_impressions.parquet                         billing export
    viewer_feedback.jsonl                          app reviews and tickets
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Chosen, not arbitrary. Seeds were scanned for a reveal that reads cleanly on a
# projector: the planted titles must sweep the naive top 3 AND be absent from the
# corrected top 5, with no near-identical title names spanning the two lists.
# Changing it invalidates every number in instructor/RUNBOOK.md.
SEED = 42

# The dataset covers ANCHOR_END and the 59 days before it. Fixed rather than
# relative to "today" so the committed files, the runbook numbers and any saved
# Genie answer all stay in agreement. Pass --anchor-end to re-anchor later; the
# row counts and the planted mistakes do not change when you do.
ANCHOR_END = dt.date(2026, 9, 17)
DAYS = 60

N_HOUSEHOLD = 3_000
N_SESSION = 300_000
N_ADVERTISER = 40
N_FEEDBACK = 400
DUP_RATE = 0.003        # at-least-once delivery duplicates
NULL_PLATFORM_RATE = 0.005
MISSING_CHANNEL_RATE = 0.04
SESSIONS_WITH_ADS = 60_000
SLOTS_PER_SESSION = 3

# Households where household_id % POOR_QOE_MOD == 0 stream over a bad
# connection. Playback and feedback both key off this, so rebuffering
# complaints line up with rebuffer_seconds for anyone who checks.
POOR_QOE_MOD = 12

# Dayparts, and the boundaries every downstream question depends on. The
# broadcast day runs 06:00 to 06:00, which is why Overnight sits at the END of
# its broadcast day rather than the start of a calendar one.
DAYPARTS = [
    ("Early Morning", 1, 6, 9, "6a-10a", 0.85),
    ("Daytime", 2, 10, 15, "10a-4p", 0.80),
    ("Early Fringe", 3, 16, 19, "4p-8p", 1.00),
    ("Prime", 4, 20, 22, "8p-11p", 1.35),
    ("Late Fringe", 5, 23, 23, "11p-12a", 1.15),
    ("Overnight", 6, 0, 5, "12a-6a", 0.55),
]

# Hour-of-day viewing weights: a real prime peak, and enough overnight mass
# that the broadcast-day question has something to bite on.
HOUR_WEIGHTS = [
    2.8, 2.2, 1.8, 1.5, 1.4, 1.6,      # 00-05  overnight
    2.4, 3.0, 3.2, 3.0, 2.9, 3.0,      # 06-11
    3.2, 3.3, 3.4, 3.6, 4.2, 5.4,      # 12-17
    6.8, 8.2, 10.5, 10.8, 8.4, 5.0,    # 18-23
]

NETWORKS = {
    "Tidewater": {
        "n": 34,
        "genres": ["Drama", "Procedural", "True Crime"],
        "types": [("series_episode", 0.74), ("movie", 0.14), ("live_event", 0.12)],
        "base_cpm": 18.0,
        # Deliberately no near-homophones in one list. "Night" and "Ninth"
        # both here produced "Night Circuit" and "Ninth Circuit" in the same
        # before/after screenshot, which reads as a typo rather than a finding.
        "first": ["Cold", "Iron", "Silver", "Broken", "Last", "Night", "Crimson",
                  "Hollow", "Steel", "Quiet", "Burning", "Tenth"],
        "second": ["Precinct", "Harbor", "Verdict", "Circuit", "Alibi", "Corridor",
                   "Territory", "Ledger", "Frontier", "Divide"],
    },
    "Nova": {
        "n": 28,
        "genres": ["Sci-Fi", "Fantasy", "Horror"],
        "types": [("series_episode", 0.78), ("movie", 0.22)],
        "base_cpm": 13.0,
        "first": ["Void", "Quantum", "Orbit", "Ash", "Ember", "Static", "Fracture",
                  "Nebula", "Pale", "Outer"],
        "second": ["Directive", "Expanse", "Descent", "Reactor", "Colony", "Vector",
                   "Threshold", "Anomaly", "Drift", "Gate"],
    },
    "Meridian News": {
        "n": 26,
        "genres": ["Business News", "Politics", "Personal Finance"],
        "types": [("news_program", 0.58), ("live_block", 0.42)],
        "base_cpm": 30.0,
        "first": ["Market", "Closing", "Opening", "Capital", "Balance", "Morning",
                  "Evening", "Daily"],
        "second": ["Signal", "Bell", "Brief", "Desk", "Report", "Watch", "Exchange",
                   "Hour", "Roundtable"],
    },
}

DMAS = [
    "Providence RI", "Boston MA", "New York NY", "Hartford CT", "Philadelphia PA",
    "Chicago IL", "Los Angeles CA", "Atlanta GA", "Dallas-Ft Worth TX", "Seattle WA",
    "Denver CO", "Phoenix AZ", "Miami FL", "Detroit MI", "Minneapolis MN",
    "Portland OR", "Nashville TN", "Baltimore MD", "St Louis MO", "Columbus OH",
]
DEVICE_CLASSES = ["Roku", "Fire TV Stick", "Apple TV", "Samsung TV", "iPhone",
                  "Android phone", "iPad", "Web browser"]
PLATFORMS = [
    ("linear_set_top", 0.30), ("ctv_roku", 0.17), ("ctv_firetv", 0.12),
    ("ctv_appletv", 0.09), ("app_ios", 0.11), ("app_android", 0.09),
    ("web", 0.08), ("ctv_samsung", 0.04),
]
TIERS = [("Basic", 0.34), ("Standard", 0.38), ("Premium", 0.21), ("Premium Ad-Free", 0.07)]

AD_CATEGORIES = [
    ("Automotive", 1.35), ("Pharmaceutical", 1.55), ("Financial Services", 1.30),
    ("Quick Service Restaurant", 0.85), ("Retail", 0.90), ("Telecom", 1.10),
    ("Consumer Packaged Goods", 0.80), ("Travel & Leisure", 1.05),
    ("Insurance", 1.20), ("Technology", 1.15), ("Direct Response", 0.55),
]
# No agency shares a name with a network. "Meridian Media" the agency next to
# "Meridian News" the network is the kind of ambiguity that eats five minutes of
# a workshop for no teaching value.
AGENCIES = ["Kingfisher Media", "Northgate Group", "Blue Harbor Partners",
            "Cascade Buying", "Rowan Reach", "Direct / In-House"]
AD_PREFIX = ["Apex", "Northwind", "Vantage", "Clearline", "Summit", "Harbor",
             "Pioneer", "Cardinal", "Granite", "Lakeside", "Silverline"]
AD_SUFFIX = ["Motors", "Health", "Financial", "Foods", "Wireless", "Outfitters",
             "Airways", "Insurance", "Systems", "Brands", "Labs", "Energy"]

# --- Trap 1: the channel-surf tail in watch_seconds -------------------------
# Three titles on Tidewater get heavy promotion (high volume) and a 76% chance
# that any given session is a channel surf of 3-29 seconds. They finish first,
# second and third on a naive COUNT(*) and drop out of the top five the moment
# anyone applies the 30-second qualified-view rule.
#
# This is arithmetic, not luck. Relative session volume is proportional to
# popularity_weight, and relative QUALIFIED volume to
# weight * (1 - surf_propensity). Setting the trap weights relative to the best
# normal title guarantees both margins, and the assertions below fail here
# rather than in front of a room.
TRAP_COUNT = 3
TRAP_SURF = 0.76
TRAP_MULTIPLIERS = [2.10, 2.00, 1.90]
TRAP_NETWORK = "Tidewater"

# --- Trap 2: unsold ad slots ------------------------------------------------
# Only filled slots earn money. Averaging revenue_usd over every slot, unsold
# ones included, understates the real rate by about 30%.
FILL_MIX = [("filled", 0.70), ("unfilled", 0.23), ("house", 0.07)]

FEEDBACK_TEMPLATES = {
    "buffering": [
        "Constant buffering every night, unwatchable on my {device}.",
        "Spins forever before anything plays. {device} app is the worst offender.",
        "Show freezes every few minutes. Paying for this?",
        "Stream keeps dropping to potato quality and then stalling out.",
    ],
    "content": [
        "Love the new season, please renew it.",
        "Wish there were more episodes of the {genre} shows.",
        "Great lineup lately, the {genre} block is my favorite.",
        "Why did you remove half the catalog?",
    ],
    "ads": [
        "Way too many ad breaks, and the same ad four times in a row.",
        "Ads are louder than the show.",
        "I pay monthly and still get five minutes of commercials.",
    ],
    "app": [
        "App crashes on launch since the last update on {device}.",
        "Cannot find the continue watching row anymore, the redesign is confusing.",
        "Login loops back to the sign-in screen every time.",
    ],
    "billing": [
        "Charged twice this month, support has not replied.",
        "Cancelled last month and was billed anyway.",
    ],
}
CHANNELS = [("app_store_review", 0.42), ("support_ticket", 0.28),
            ("in_app_survey", 0.20), ("social", 0.10)]


def weighted_choice(rng: random.Random, pairs):
    r = rng.random()
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if r < acc:
            return value
    return pairs[-1][0]


def weighted_array(rng: np.random.Generator, pairs, size):
    values = [p[0] for p in pairs]
    probs = np.array([p[1] for p in pairs], dtype=float)
    probs /= probs.sum()
    return rng.choice(values, size=size, p=probs)


def daypart_of_hour(hour: int) -> str:
    for name, _order, lo, hi, _label, _mult in DAYPARTS:
        if lo <= hour <= hi:
            return name
    return "Overnight"


def build_content(rng: random.Random):
    """The programming catalog, plus the private generator parameters."""
    rows = []
    content_id = 100_000
    today = ANCHOR_END

    for network, spec in NETWORKS.items():
        used, series_pool = set(), []
        for _ in range(spec["n"]):
            content_id += 1
            ctype = weighted_choice(rng, spec["types"])
            genre = rng.choice(spec["genres"])

            if ctype == "series_episode" and series_pool and rng.random() < 0.72:
                series_title = rng.choice(series_pool)
                season = rng.randint(1, 5)
                episode = rng.randint(1, 18)
                title = f"{series_title} S{season:02d}E{episode:02d}"
            else:
                candidate = f"{rng.choice(spec['first'])} {rng.choice(spec['second'])}"
                for _attempt in range(60):
                    if candidate not in used:
                        break
                    candidate = f"{rng.choice(spec['first'])} {rng.choice(spec['second'])}"
                used.add(candidate)
                series_title = candidate
                if ctype == "series_episode":
                    series_pool.append(candidate)
                    season, episode = 1, rng.randint(1, 12)
                    title = f"{candidate} S01E{episode:02d}"
                else:
                    season = episode = None
                    title = candidate

            runtime = {
                "movie": lambda: rng.choice([88, 94, 101, 108, 115, 122]),
                "live_event": lambda: rng.choice([120, 180, 240]),
                "live_block": lambda: rng.choice([60, 120, 180]),
                "news_program": lambda: rng.choice([30, 60]),
            }.get(ctype, lambda: rng.choice([30, 45, 60]))()

            # Live news blocks are natural surf magnets: people check the
            # market number and leave. Scripted drama holds an audience.
            if ctype == "live_block":
                surf = rng.uniform(0.42, 0.58)
            elif ctype == "live_event":
                surf = rng.uniform(0.22, 0.34)
            else:
                surf = rng.uniform(0.07, 0.16)

            rows.append({
                "content_id": content_id,
                "title": title,
                "series_title": series_title,
                "network": network,
                "content_type": ctype,
                "genre": genre,
                "season_number": season,
                "episode_number": episode,
                "runtime_minutes": runtime,
                "premiere_date": today - dt.timedelta(days=rng.randint(30, 1400)),
                "is_original": rng.random() < 0.38,
                "surf_propensity": round(surf, 4),
                "popularity_weight": round(math.exp(rng.gauss(0, 0.85)), 6),
                "is_trap_title": False,
            })

    return plant_trap_one(rows)


def plant_trap_one(rows):
    """Guarantee the rank swap that the whole workshop turns on."""
    trap_net = sorted(
        [r for r in rows if r["network"] == TRAP_NETWORK],
        key=lambda r: r["popularity_weight"],
        reverse=True,
    )
    # Highest weight among normal titles once the top three are reassigned.
    w_next = trap_net[TRAP_COUNT]["popularity_weight"]

    trap_titles = []
    for row, mult in zip(trap_net[:TRAP_COUNT], TRAP_MULTIPLIERS):
        row["popularity_weight"] = round(w_next * mult, 6)
        row["surf_propensity"] = TRAP_SURF
        row["is_trap_title"] = True
        trap_titles.append(row["title"])

    normals = trap_net[TRAP_COUNT:]
    best_raw = max(n["popularity_weight"] for n in normals)
    best_qual = max(n["popularity_weight"] * (1 - n["surf_propensity"]) for n in normals)
    trap_raw_min = min(t["popularity_weight"] for t in trap_net[:TRAP_COUNT])
    trap_qual_max = max(t["popularity_weight"] * (1 - TRAP_SURF)
                        for t in trap_net[:TRAP_COUNT])

    raw_margin = trap_raw_min / best_raw
    qual_margin = best_qual / trap_qual_max
    print(f"  trap 1 raw margin      : {raw_margin:.2f}x  (need > 1.30)")
    print(f"  trap 1 qualified margin: {qual_margin:.2f}x  (need > 1.25)")
    assert raw_margin > 1.30, (
        f"Trap titles would not sweep the naive COUNT(*) ranking ({raw_margin:.2f}x). "
        "Raise TRAP_MULTIPLIERS.")
    assert qual_margin > 1.25, (
        f"Trap titles would survive the 30-second filter ({qual_margin:.2f}x). "
        "Raise TRAP_SURF or lower TRAP_MULTIPLIERS.")

    return rows, trap_titles


def build_households(rng: np.random.Generator, pyrng: random.Random):
    hh = pd.DataFrame({"household_id": np.arange(1, N_HOUSEHOLD + 1, dtype=np.int64)})
    hh["dma"] = rng.choice(DMAS, size=N_HOUSEHOLD)
    hh["subscription_tier"] = weighted_array(rng, TIERS, N_HOUSEHOLD)
    hh["primary_device"] = rng.choice(DEVICE_CLASSES, size=N_HOUSEHOLD)
    signup_offsets = rng.integers(20, 1600, size=N_HOUSEHOLD)
    hh["signup_date"] = [
        (ANCHOR_END - dt.timedelta(days=int(d))).isoformat() for d in signup_offsets
    ]
    # CSV export from an operational system: booleans arrive as text.
    hh["is_active"] = np.where(rng.random(N_HOUSEHOLD) > 0.06, "true", "false")
    return hh


def build_advertisers(rng: random.Random):
    rows = []
    for i in range(N_ADVERTISER):
        category, multiplier = rng.choice(AD_CATEGORIES)
        rows.append({
            "advertiser_id": 2000 + i,
            "advertiser_name": f"{rng.choice(AD_PREFIX)} {rng.choice(AD_SUFFIX)}",
            "category": category,
            "agency": rng.choice(AGENCIES),
            "buy_type": weighted_choice(rng, [("National", 0.45), ("Regional", 0.35),
                                              ("Local", 0.20)]),
            "cpm_multiplier": round(multiplier, 3),
        })
    return pd.DataFrame(rows)


def build_playback(rng: np.random.Generator, content: pd.DataFrame):
    """Playback telemetry. Trap 1 lives in watch_seconds."""
    weights = content["popularity_weight"].to_numpy(dtype=float)
    weights = weights / weights.sum()
    idx = rng.choice(len(content), size=N_SESSION, p=weights)

    content_id = content["content_id"].to_numpy()[idx]
    surf_propensity = content["surf_propensity"].to_numpy(dtype=float)[idx]
    runtime_minutes = content["runtime_minutes"].to_numpy(dtype=float)[idx]
    content_type = content["content_type"].to_numpy()[idx]

    hour_probs = np.array(HOUR_WEIGHTS, dtype=float)
    hour_probs /= hour_probs.sum()
    hour = rng.choice(24, size=N_SESSION, p=hour_probs)
    minute = rng.integers(0, 60, size=N_SESSION)
    second = rng.integers(0, 60, size=N_SESSION)
    day_offset = rng.integers(0, DAYS, size=N_SESSION)

    household_id = rng.integers(1, N_HOUSEHOLD + 1, size=N_SESSION)

    # --- Trap 1 ---
    # A surf session is 3-29 seconds and never clears the 30-second bar. A real
    # view runs a plausible fraction of the asset's runtime, floored at 30.
    is_surf = rng.random(N_SESSION) < surf_propensity
    surf_seconds = (rng.random(N_SESSION) * 26 + 3).astype(np.int32)
    real_seconds = np.maximum(
        30,
        (runtime_minutes * 60 * (0.18 + 0.82 * np.power(rng.random(N_SESSION), 0.75)))
        .astype(np.int32),
    )
    watch_seconds = np.where(is_surf, surf_seconds, real_seconds).astype(np.int32)

    # Quality of experience: one household in twelve has a bad connection.
    poor_qoe = (household_id % POOR_QOE_MOD) == 0
    rebuffer = np.zeros(N_SESSION)
    poor_hit = poor_qoe & (rng.random(N_SESSION) < 0.62) & (watch_seconds >= 30)
    rebuffer[poor_hit] = np.round(rng.random(poor_hit.sum()) * 42 + 3, 2)
    minor_hit = (~poor_qoe) & (rng.random(N_SESSION) < 0.08) & (watch_seconds >= 30)
    rebuffer[minor_hit] = np.round(rng.random(minor_hit.sum()) * 7, 2)
    startup_ms = np.where(
        poor_qoe,
        (rng.random(N_SESSION) * 5200 + 1400).astype(np.int32),
        (rng.random(N_SESSION) * 1600 + 350).astype(np.int32),
    )

    start_dates = np.array(
        [ANCHOR_END - dt.timedelta(days=int(d)) for d in day_offset], dtype=object
    )
    # Landing dirt: the timestamp arrives as an ISO string, because upstream
    # serialized it through JSON on the way out.
    start_ts = [
        f"{d.isoformat()}T{h:02d}:{m:02d}:{s:02d}"
        for d, h, m, s in zip(start_dates, hour, minute, second)
    ]

    platform = weighted_array(rng, PLATFORMS, N_SESSION).astype(object)
    # Landing dirt: some events arrive with no platform at all.
    platform[rng.random(N_SESSION) < NULL_PLATFORM_RATE] = None

    df = pd.DataFrame({
        "session_id": [f"s_{i:09d}" for i in range(N_SESSION)],
        "household_id": household_id.astype(np.int64),
        "content_id": content_id.astype(np.int64),
        "device_id": [f"d_{h}_{v}" for h, v in
                      zip(household_id, rng.integers(1, 4, size=N_SESSION))],
        "start_ts": start_ts,
        "watch_seconds": watch_seconds,
        "platform": platform,
        "is_live": np.isin(content_type, ["live_event", "live_block"]),
        "rebuffer_seconds": rebuffer,
        "startup_ms": startup_ms,
        "ingest_date": [d.isoformat() for d in start_dates],
    })

    # Landing dirt: at-least-once delivery means some sessions land twice.
    dup_n = int(N_SESSION * DUP_RATE)
    dup_idx = rng.choice(N_SESSION, size=dup_n, replace=False)
    df = pd.concat([df, df.iloc[dup_idx]], ignore_index=True)

    # Shuffle so the duplicates are not all bunched at the end, which would
    # give the game away the moment anyone scrolled to the bottom.
    order = rng.permutation(len(df))
    return df.iloc[order].reset_index(drop=True), is_surf


def build_ad_impressions(rng: np.random.Generator, playback: pd.DataFrame,
                         content: pd.DataFrame, advertisers: pd.DataFrame):
    """One row per ad slot opportunity. Trap 2 lives in fill_status."""
    # Ads only run inside content someone actually watched for a while.
    eligible = playback.loc[
        playback["watch_seconds"] >= 60, ["session_id", "household_id", "content_id",
                                         "start_ts"]
    ].drop_duplicates(subset="session_id")
    take = min(SESSIONS_WITH_ADS, len(eligible))
    picked = eligible.iloc[rng.choice(len(eligible), size=take, replace=False)]

    base = picked.loc[picked.index.repeat(SLOTS_PER_SESSION)].reset_index(drop=True)
    n = len(base)

    net_by_content = dict(zip(content["content_id"], content["network"]))
    base_cpm_by_net = {name: spec["base_cpm"] for name, spec in NETWORKS.items()}

    # An impression happens somewhere inside the session, not at its start.
    start = pd.to_datetime(base["start_ts"])
    offset_minutes = rng.integers(2, 55, size=n)
    impression_ts = start + pd.to_timedelta(offset_minutes, unit="m")

    hours = impression_ts.dt.hour.to_numpy()
    daypart = np.array([daypart_of_hour(int(h)) for h in hours])
    daypart_mult = np.array([
        dict((d[0], d[5]) for d in DAYPARTS)[dp] for dp in daypart
    ])

    fill_status = weighted_array(rng, FILL_MIX, n)
    filled = fill_status == "filled"

    adv_idx = rng.choice(len(advertisers), size=n)
    advertiser_id = advertisers["advertiser_id"].to_numpy()[adv_idx].astype(object)
    adv_mult = advertisers["cpm_multiplier"].to_numpy(dtype=float)[adv_idx]

    network = np.array([net_by_content[c] for c in base["content_id"]])
    net_cpm = np.array([base_cpm_by_net[nw] for nw in network])

    cpm = np.where(
        filled,
        np.round(net_cpm * adv_mult * daypart_mult * (0.92 + 0.16 * rng.random(n)), 2),
        0.0,
    )
    revenue = np.round(cpm / 1000.0, 6)

    advertiser_id[~filled] = None
    campaign_id = np.array(
        [f"cmp_{int(a)}_{int(k)}" if a is not None else None
         for a, k in zip(advertiser_id, rng.integers(1, 6, size=n))],
        dtype=object,
    )

    return pd.DataFrame({
        "impression_id": [f"i_{i:09d}" for i in range(n)],
        "pod_id": [f"p_{s}_{k}" for s, k in
                   zip(base["session_id"], rng.integers(1, 4, size=n))],
        "session_id": base["session_id"].to_numpy(),
        "household_id": base["household_id"].to_numpy().astype(np.int64),
        "content_id": base["content_id"].to_numpy().astype(np.int64),
        "advertiser_id": advertiser_id,
        "campaign_id": campaign_id,
        "impression_ts": impression_ts.dt.strftime("%Y-%m-%dT%H:%M:%S").to_numpy(),
        "daypart": daypart,
        "pod_position": rng.integers(1, 5, size=n).astype(np.int32),
        "ad_seconds": rng.choice([15, 30, 30, 30, 60], size=n).astype(np.int32),
        "fill_status": fill_status,
        # Landing dirt: the billing export ships money as text.
        "cpm": [f"{v:.2f}" for v in cpm],
        "revenue_usd": [f"{v:.6f}" for v in revenue],
        "ingest_date": impression_ts.dt.strftime("%Y-%m-%d").to_numpy(),
    })


def build_feedback(rng: np.random.Generator, pyrng: random.Random,
                   households: pd.DataFrame):
    """Free-text feedback as JSON lines, with a key that is sometimes absent."""
    hh_ids = households["household_id"].to_numpy()
    device_by_hh = dict(zip(households["household_id"], households["primary_device"]))

    # Poor-connectivity households complain about buffering at a much higher
    # rate. Anyone who joins this back to rebuffer_seconds will find it holds.
    poor = hh_ids[(hh_ids % POOR_QOE_MOD) == 0]
    normal = hh_ids[(hh_ids % POOR_QOE_MOD) != 0]

    records = []
    for i in range(N_FEEDBACK):
        from_poor = pyrng.random() < 0.45
        hh = int(pyrng.choice(list(poor if from_poor else normal)))
        theme = ("buffering" if from_poor and pyrng.random() < 0.7
                 else weighted_choice(pyrng, [("content", 0.34), ("ads", 0.24),
                                              ("app", 0.24), ("billing", 0.10),
                                              ("buffering", 0.08)]))
        template = pyrng.choice(FEEDBACK_TEMPLATES[theme])
        text = template.format(device=device_by_hh[hh],
                               genre=pyrng.choice(["true crime", "sci-fi", "drama",
                                                   "business news"]))
        rating = {"buffering": [1, 1, 2, 2, 3], "ads": [1, 2, 2, 3, 3],
                  "app": [1, 2, 2, 3], "billing": [1, 1, 2],
                  "content": [3, 4, 4, 5, 5]}[theme]
        submitted = ANCHOR_END - dt.timedelta(days=pyrng.randint(0, DAYS - 1))
        record = {
            "feedback_id": f"f_{i:06d}",
            "household_id": hh,
            "submitted_ts": f"{submitted.isoformat()}T"
                            f"{pyrng.randint(0, 23):02d}:{pyrng.randint(0, 59):02d}:00",
            # Landing dirt: the rating comes through as a string.
            "star_rating": str(pyrng.choice(rating)),
            "source_channel": weighted_choice(pyrng, CHANNELS),
            "review_text": text,
        }
        # Landing dirt: on some records the key is absent entirely, which is
        # different from being null and breaks a naive schema assumption.
        if pyrng.random() < MISSING_CHANNEL_RATE:
            del record["source_channel"]
        records.append(record)

    return records


def verify(content: pd.DataFrame, playback: pd.DataFrame,
           impressions: pd.DataFrame) -> dict:
    """Prove the traps land, against the generated data rather than the plan."""
    joined = playback.merge(
        content[["content_id", "title", "series_title", "network", "is_trap_title"]],
        on="content_id",
    )
    trap_net = joined[joined["network"] == TRAP_NETWORK]

    raw = (trap_net.groupby("title")
           .size().sort_values(ascending=False).head(6))
    qual = (trap_net[trap_net["watch_seconds"] >= 30]
            .groupby("title").size().sort_values(ascending=False).head(6))

    trap_titles = set(content.loc[content["is_trap_title"], "title"])
    raw_top3 = list(raw.index[:3])
    qual_top5 = list(qual.index[:5])

    print(f"\n  {TRAP_NETWORK} — naive COUNT(*) top 6:")
    for title, n in raw.items():
        print(f"    {n:>7,}  {title}{'   <-- planted' if title in trap_titles else ''}")
    print(f"\n  {TRAP_NETWORK} — qualified (watch_seconds >= 30) top 6:")
    for title, n in qual.items():
        print(f"    {n:>7,}  {title}{'   <-- planted' if title in trap_titles else ''}")

    assert set(raw_top3) == trap_titles, (
        f"Trap titles do not sweep the naive top 3. Got {raw_top3}.")
    assert not (trap_titles & set(qual_top5)), (
        f"A trap title survived into the qualified top 5: "
        f"{sorted(trap_titles & set(qual_top5))}")

    # Not a correctness condition, but it matters in the room: if the corrected
    # ranking is topped by another episode of a planted series, "all three
    # disappeared" invites an argument instead of a nod.
    series_by_title = dict(zip(content["title"], content["series_title"]))
    trap_series = {series_by_title[t] for t in trap_titles}
    clash = sorted({t for t in qual_top5 if series_by_title[t] in trap_series})
    print(f"\n  series overlap between planted titles and qualified top 5: "
          f"{clash or 'none'}")

    # Same reasoning, one level down: two titles that merely look alike side by
    # side on a projector will get read as a typo.
    confusable = sorted({
        f"{a} / {b}"
        for a in trap_titles for b in qual_top5
        if difflib.SequenceMatcher(None, a, b).ratio() > 0.62
    })
    print(f"  confusable title pairs across the reveal: {confusable or 'none'}")

    # Where the naive winner actually ends up once the rule is applied. This is
    # the single most useful sentence an instructor can say out loud.
    full_qual = (trap_net[trap_net["watch_seconds"] >= 30]
                 .groupby("title").size().sort_values(ascending=False))
    naive_winner = raw.index[0]
    true_rank = int(full_qual.index.get_loc(naive_winner)) + 1
    print(f"\n  the naive #1 ({naive_winner}) is really #{true_rank} "
          f"of {len(full_qual)} qualified titles on {TRAP_NETWORK}")

    rev = impressions["revenue_usd"].astype(float)
    filled = impressions["fill_status"] == "filled"
    naive_rate = rev.mean()
    true_rate = rev[filled].mean()
    print(f"\n  trap 2: revenue per slot, all slots      ${naive_rate:.5f}")
    print(f"          revenue per slot, filled only    ${true_rate:.5f}"
          f"   ({true_rate / naive_rate:.2f}x)")
    assert true_rate / naive_rate > 1.30, "Trap 2 understatement is too small to notice."

    overnight = playback["start_ts"].str.slice(11, 13).astype(int) < 6
    print(f"\n  trap 3: sessions starting before 06:00   {overnight.sum():,}"
          f"   ({100 * overnight.mean():.1f}% of rows)")
    assert overnight.mean() > 0.08, "Not enough overnight mass for the broadcast-day trap."

    return {
        "trap_titles": sorted(trap_titles),
        "naive_top3": raw_top3,
        "qualified_top5": qual_top5,
        "naive_winner": naive_winner,
        "naive_winner_true_rank": true_rank,
        "qualified_titles_on_trap_network": len(full_qual),
        "naive_revenue_per_slot": round(float(naive_rate), 6),
        "filled_revenue_per_slot": round(float(true_rate), 6),
        "qualified_share_pct": round(
            100 * float((playback["watch_seconds"] >= 30).mean()), 2),
    }


def main() -> None:
    global ANCHOR_END, SEED

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
    parser.add_argument("--anchor-end", default=ANCHOR_END.isoformat(),
                        help="Last day covered by the dataset (YYYY-MM-DD). "
                             "Re-anchor to keep 'last month' questions meaningful.")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="Changing this changes which titles get planted, so it "
                             "invalidates every number in the runbook. Rerun and "
                             "update them together.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify the traps and print the summary without writing files.")
    args = parser.parse_args()

    ANCHOR_END = dt.date.fromisoformat(args.anchor_end)
    SEED = args.seed
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"seed {SEED}, window {ANCHOR_END - dt.timedelta(days=DAYS - 1)} "
          f"to {ANCHOR_END}\n")

    pyrng = random.Random(SEED)
    rng = np.random.default_rng(SEED)

    content_rows, trap_titles = build_content(pyrng)
    content = pd.DataFrame(content_rows)
    households = build_households(rng, pyrng)
    advertisers = build_advertisers(pyrng)
    playback, _ = build_playback(rng, content)
    impressions = build_ad_impressions(rng, playback, content, advertisers)
    feedback = build_feedback(rng, pyrng, households)

    facts = verify(content, playback, impressions)

    if args.dry_run:
        print("\n  --dry-run: nothing written.")
        return

    # --- write the landing files ---
    # CSV keeps every value as text, exactly as an operational export does.
    content_csv = content.drop(columns=["surf_propensity", "popularity_weight",
                                        "is_trap_title"]).copy()
    content_csv["premiere_date"] = content_csv["premiere_date"].map(lambda d: d.isoformat())
    content_csv["is_original"] = content_csv["is_original"].map(
        lambda b: "true" if b else "false")
    content_csv["season_number"] = content_csv["season_number"].map(
        lambda v: "" if v is None or (isinstance(v, float) and math.isnan(v)) else int(v))
    content_csv["episode_number"] = content_csv["episode_number"].map(
        lambda v: "" if v is None or (isinstance(v, float) and math.isnan(v)) else int(v))
    content_csv.to_csv(out / "content.csv", index=False)

    households.to_csv(out / "households.csv", index=False)
    advertisers.drop(columns=["cpm_multiplier"]).to_csv(
        out / "advertisers.csv", index=False)

    pq.write_table(pa.Table.from_pandas(playback, preserve_index=False),
                   out / "playback_events.parquet", compression="snappy")
    pq.write_table(pa.Table.from_pandas(impressions, preserve_index=False),
                   out / "ad_impressions.parquet", compression="snappy")

    with open(out / "viewer_feedback.jsonl", "w") as fh:
        for record in feedback:
            fh.write(json.dumps(record) + "\n")

    print("\n  files written to", out)
    total = 0
    for path in sorted(out.iterdir()):
        if path.name.startswith("."):
            continue
        size = path.stat().st_size
        total += size
        print(f"    {size / 1_048_576:>7.2f} MB  {path.name}")
    print(f"    {total / 1_048_576:>7.2f} MB  total")

    print(f"\n  rows: {len(content)} content, {len(households):,} households, "
          f"{len(advertisers)} advertisers,\n        {len(playback):,} playback events "
          f"({int(len(playback) * DUP_RATE / (1 + DUP_RATE)):,} of them duplicates), "
          f"\n        {len(impressions):,} ad slots, {len(feedback)} feedback records")

    print("\n  planted titles (trap 1):")
    for title in facts["trap_titles"]:
        print("   ", title)
    print(f"\n  qualified share of all sessions: {facts['qualified_share_pct']}%")
    print("\n  Numbers above belong in instructor/RUNBOOK.md. Regenerating with the "
          "same\n  seed reproduces them exactly.")


if __name__ == "__main__":
    main()
