"""Global configuration for the LuckyScoin bot.

Update-related constants live here so that a version bump only
touches this file. Do not commit secrets here.
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

# === SEASONS ===

# Length of a season in days.
SEASON_DURATION_DAYS = 20

# Reward for the top 3 at season end (roulette tickets).
SEASON_REWARD_TICKETS = {1: 5, 2: 3, 3: 2}

# Set to False to put the casino into "reconstruction" mode.
TYCOON_ENABLED = False

# Shown on the placeholder screen.
TYCOON_COMING_VERSION = "1.2.0"
