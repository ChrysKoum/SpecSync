"""Data models for the example service."""
from pydantic import BaseModel


class User(BaseModel):
    """User model representing a system user."""
    id: int
    username: str
    email: str
