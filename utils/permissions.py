"""
Permission helpers.

Hierarchy:
  Owner  (OWNER_ID env var) → full access
  Admin  (stored in MongoDB) → management commands
  User   → no access
"""
from config import Config


async def is_owner(user_id: int) -> bool:
    return user_id == Config.OWNER_ID


async def is_admin(user_id: int, db) -> bool:
    """Owner is implicitly an admin."""
    if user_id == Config.OWNER_ID:
        return True
    return await db.is_admin(user_id)
