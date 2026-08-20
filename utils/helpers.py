"""Miscellaneous helper utilities."""


def format_number(n: int) -> str:
    """Return n formatted with thousands separator."""
    return f"{n:,}"


def format_uptime(seconds: float) -> str:
    """Convert raw seconds to a human-readable uptime string."""
    secs = int(seconds)
    days, secs     = divmod(secs, 86_400)
    hours, secs    = divmod(secs, 3_600)
    minutes, secs  = divmod(secs, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def keyword_list_text(keywords: list) -> str:
    """Render a numbered keyword list for display inside a Telegram message."""
    if not keywords:
        return "_No keywords configured._"
    return "\n".join(f"{i + 1}. `{kw}`" for i, kw in enumerate(keywords))
