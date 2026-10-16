# Changelog

## Unreleased
- Restored purchasable titles: 🍀 Клевер, 💎 Бриллиант, 🔥 Огненный, 👑 Королевский, 🎩 Лорд, 🐋 Кит.
- Restored level titles: 🎲 Новичок, 🍀 Везунчик, 💎 Богач, 🔥 Хайроллер, 👑 Легенда.
- Default title for new players is now "🎲 Новичок".
- One-shot migration of legacy title inventory rows (item_id 1..6 → shop_id 101..106).
- Fixed badge HP preservation across re-equip and slot swaps.
- Broken badges are now removed from inventory.
- Hidden badges (d6_shard) no longer drop from slot machines.
- Roulette prizes: corrected weights to 100% and dynamic UI.
- Maintenance middleware no longer lets /admin bypass the lock.
- Admin /give /take /setbalance protect against negative balances.
- Chain reaction no longer consumes bombs.
- Trade: TTL pruning + burn-fee documented.
- Centralized badge slot levels (SLOT_UNLOCK_LEVELS).
- Cached purchasable cosmetic IDs.
- safe_answer moved to utils.py.
- Read-only DB methods no longer create user rows.