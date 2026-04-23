def get_user_name(user: dict) -> str:
    """Return user['name'], or 'anonymous' if no name is present."""
    return user.get("nam", "anonymous")
