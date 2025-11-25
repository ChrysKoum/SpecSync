"""User endpoint handlers."""
from fastapi import APIRouter, HTTPException
from backend.models import User

router = APIRouter()

# Sample user data for demonstration
USERS = [
    User(id=1, username="alice", email="alice@example.com"),
    User(id=2, username="bob", email="bob@example.com"),
    User(id=3, username="charlie", email="charlie@example.com"),
]


@router.get("/users")
async def list_users():
    """
    List all users in the system.
    
    Returns:
        list[User]: Array of user objects
    """
    return USERS


@router.get("/users/{id}")
async def get_user(id: int):
    """
    Get a specific user by their ID.
    
    Args:
        id: Unique identifier for the user
        
    Returns:
        User: User object if found
        
    Raises:
        HTTPException: 404 if user not found
    """
    for user in USERS:
        if user.id == id:
            return user
    
    raise HTTPException(status_code=404, detail="User not found")

@router.get("/users/{id}/posts")
async def get_user_posts(id: int):
    return {"user_id": id, "posts": []}