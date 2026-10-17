"""Global configuration for the LuckyScoin bot.

Update-related constants live here so that a version bump only
touches this file. Do not commit secrets here.

DAILY_WHEEL_PRIZES EV must stay below 1000 LC to avoid inflation.
"""

# === 1.0.0 UPDATE ===

# File ID of the celebration GIF (animation), obtained via
# @RawDataBot. It belongs to THIS bot — do not share it with
# other bots or it will fail.
UPDATE_GIF_FILE_ID = (
    "CgACAgIAAxkBAAFWI0xq0QwE06tgvaKmFnwAARuMVUjaJFYAAmCvAAKJDYlKv8lD3CR0ErM9BA"
)

# Version shown on the celebration screen.
UPDATE_VERSION = "1.0.0"

# Title that becomes available for 2 days after the update.
UPDATE_GIFT_TITLE_ID = "old"

# Number of days the "Old" title stays claimable.
UPDATE_GIFT_TITLE_DAYS = 2

# Tiered LC → SC conversion used at update time.
# Each tuple: (upper_bound_of_tier_in_LC or None, LC_per_1_SC).
# The last tier MUST have None to catch all remaining LC.
CONVERSION_TIERS = [
    (100_000, 500),
    (None,    5_000),
]

# === DAILY REWARDS ===

# Each tuple: (day_index, LC amount). Day 7 also guarantees a wheel spin.
DAILY_REWARDS = [
    (1, 50),
    (2, 100),
    (3, 200),
    (4, 350),
    (5, 500),
    (6, 750),
    (7, 1_500),
]

# Chance for a wheel spin on any non-final day.
DAILY_WHEEL_CHANCE = 0.15

# Minimum time between wheel spins for a player.
DAILY_WHEEL_COOLDOWN_SECONDS = 12 * 3600

# Each dict contains the wheel symbol, display name, chance percentage,
# and LC prize amount. Chances must total 100.
DAILY_WHEEL_PRIZES = (
    {"symbol": "🥉", "name": "Bronze",  "chance": 35, "lc_amount": 100},
    {"symbol": "🥈", "name": "Silver",  "chance": 30, "lc_amount": 250},
    {"symbol": "🥇", "name": "Gold",    "chance": 20, "lc_amount": 500},
    {"symbol": "💎", "name": "Diamond", "chance": 10, "lc_amount": 1_500},
    {"symbol": "👑", "name": "Crown",   "chance": 5,  "lc_amount": 5_000},
)

# === SEASONS ===

# === HALLOWEEN 2026 ===
HALLOWEEN_START = (2026, 10, 26)
HALLOWEEN_END = (2026, 11, 1)
HALLOWEEN_JACK_END = (2026, 10, 31)

# Length of a season in days.
SEASON_DURATION_DAYS = 20

# Reward for the top 3 at season end (roulette tickets).
SEASON_REWARD_TICKETS = {1: 5, 2: 3, 3: 2}

# Set to False to put the casino into "reconstruction" mode.
TYCOON_ENABLED = False

# Shown on the placeholder screen.
TYCOON_COMING_VERSION = "1.2.0"
