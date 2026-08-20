"""
Entity-aware text replacement.

Telegram message entities carry formatting (bold, italic, URL, etc.) as
character-offset ranges in the message text.  When we replace a keyword with
a different-length replacement, every entity whose range follows the replacement
must have its offset shifted by the length delta.  Entities that *overlap* the
replacement are dropped (e.g. a MENTION entity whose text was the keyword).

Algorithm overview
──────────────────
1. Collect all keyword match positions (start, end) in the original text.
2. Sort them and remove overlapping matches (keep the first/leftmost).
3. Build the new text by stitching unchanged segments and replacements together.
4. For each original entity, determine whether it:
     a) Ends before the replacement       → shift by cumulative delta so far
     b) Starts at or after the replacement → no additional shift from this step
     c) Is completely contained by the entity (entity wraps replacement) → shrink entity
     d) Overlaps partially                 → drop (safest choice)

Pyrogram handles UTF-16 ↔ Python-string-index conversion internally, so we
work with standard Python string indices throughout.
"""
import re
import logging
from typing import List, Optional, Tuple

from pyrogram.types import MessageEntity

logger = logging.getLogger(__name__)


# ── Entity cloning ────────────────────────────────────────────────────────────

def _clone_entity(
    entity: MessageEntity, offset: int, length: int
) -> Optional[MessageEntity]:
    """Return a copy of *entity* with new *offset* / *length* fields."""
    if length <= 0:
        return None
    try:
        kwargs: dict = {"type": entity.type, "offset": offset, "length": length}
        if getattr(entity, "url", None) is not None:
            kwargs["url"] = entity.url
        if getattr(entity, "user", None) is not None:
            kwargs["user"] = entity.user
        if getattr(entity, "language", None) is not None:
            kwargs["language"] = entity.language
        if getattr(entity, "custom_emoji_id", None) is not None:
            kwargs["custom_emoji_id"] = entity.custom_emoji_id
        return MessageEntity(**kwargs)
    except Exception as exc:
        logger.debug("Could not clone entity: %s", exc)
        return None


# ── Main replacement function ─────────────────────────────────────────────────

def replace_in_text_with_entities(
    text: str,
    entities: List[MessageEntity],
    keywords: List[str],
    replacement: str,
    case_sensitive: bool = False,
) -> Tuple[str, List[MessageEntity]]:
    """
    Replace every occurrence of every keyword in *text* with *replacement*,
    and return the adjusted (new_text, new_entities) tuple.

    If no keyword is found the original (text, entities) is returned unchanged.
    """
    if not text or not keywords or replacement is None:
        return text, entities or []

    flags = 0 if case_sensitive else re.IGNORECASE

    # ── 1. Find all match positions ───────────────────────────────────────────
    raw_matches: List[Tuple[int, int]] = []
    for kw in keywords:
        if not kw:
            continue
        try:
            for m in re.finditer(re.escape(kw), text, flags):
                raw_matches.append((m.start(), m.end()))
        except re.error as exc:
            logger.warning("Regex error for keyword '%s': %s", kw, exc)

    if not raw_matches:
        return text, entities or []

    # ── 2. Sort and de-overlap (keep leftmost) ────────────────────────────────
    raw_matches.sort(key=lambda x: x[0])
    matches: List[Tuple[int, int]] = []
    last_end = -1
    for start, end in raw_matches:
        if start >= last_end:
            matches.append((start, end))
            last_end = end

    if not matches:
        return text, entities or []

    # ── 3. Build new text ─────────────────────────────────────────────────────
    parts: List[str] = []
    prev_end = 0
    for start, end in matches:
        parts.append(text[prev_end:start])
        parts.append(replacement)
        prev_end = end
    parts.append(text[prev_end:])
    new_text = "".join(parts)

    if new_text == text:
        return text, entities or []

    # ── 4. Adjust entities ────────────────────────────────────────────────────
    rep_len = len(replacement)
    new_entities: List[MessageEntity] = []

    for entity in (entities or []):
        e_start = entity.offset
        e_end   = entity.offset + entity.length

        new_e_start = e_start
        new_e_end   = e_end
        drop        = False

        for rs, re_ in matches:
            old_len = re_ - rs
            delta   = rep_len - old_len

            if re_ <= e_start:
                # Replacement is entirely BEFORE this entity → shift both bounds
                new_e_start += delta
                new_e_end   += delta

            elif rs >= e_end:
                # Replacement is entirely AFTER this entity → no change
                pass

            elif rs >= e_start and re_ <= e_end:
                # Replacement is fully WITHIN the entity → shrink end only
                new_e_end += delta

            else:
                # Partial overlap (entity straddles a replacement boundary) → drop
                drop = True
                break

        if not drop:
            cloned = _clone_entity(entity, new_e_start, new_e_end - new_e_start)
            if cloned is not None:
                new_entities.append(cloned)

    return new_text, new_entities
