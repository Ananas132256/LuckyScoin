async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except Exception:
        pass
