"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth_routes, langgraph_routes

# Create FastAPI application
app = FastAPI(
    title="Infraware Terminal API",
    description="FastAPI wrapper for LanGraph supervisor agent with authentication",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with API information.

    Returns:
        dict: API information
    """
    return {
        "name": "Infraware Terminal API",
        "version": "0.1.0",
        "endpoints": {
            "auth": "/api/auth",
            "get_auth": "/api/get-auth",
            "langgraph": "/* (proxied to LanGraph server)",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status
    """
    return {"status": "healthy"}


# Include routers (after defining root and health to avoid catch-all conflicts)
app.include_router(auth_routes.router)
app.include_router(langgraph_routes.router)
