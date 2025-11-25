"""
Example FastAPI service demonstrating SpecSync capabilities.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.handlers import health, user

app = FastAPI(
    title="Example Service",
    version="1.0.0",
    description="Example FastAPI service demonstrating SpecSync capabilities"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register health check endpoint
app.include_router(health.router)

# Register user endpoints
app.include_router(user.router)
