"""Reverse proxy routes for LanGraph endpoints."""

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from ..config import config

router = APIRouter(tags=["langgraph"])

# LanGraph server configuration
LANGGRAPH_SERVER_URL = "http://localhost:2024"


async def check_auth():
    """Check if user is authenticated.

    Raises:
        HTTPException: If user is not authenticated
    """
    if not config.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please provide an API key via /api/auth",
        )


async def proxy_request(request: Request, path: str, method: str = "GET") -> Response:
    """Proxy a request to the LanGraph server.

    Args:
        request: The incoming FastAPI request
        path: The path to proxy to
        method: HTTP method to use

    Returns:
        Response: The proxied response

    Raises:
        HTTPException: If the proxy request fails
    """
    # Build the target URL
    target_url = f"{LANGGRAPH_SERVER_URL}{path}"

    # Get query parameters
    query_params = dict(request.query_params)

    # Get request body if present
    body = None
    if method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Get headers (exclude host header)
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.request(
                method=method,
                url=target_url,
                params=query_params,
                content=body,
                headers=headers,
            )

            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="LanGraph server is not running. Please start it with 'langgraph dev'",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Request to LanGraph server timed out"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")


# Thread management endpoints
@router.post("/threads")
async def create_thread(request: Request):
    """Create a new conversation thread.

    Args:
        request: The incoming request

    Returns:
        Response: Thread creation response from LanGraph
    """
    await check_auth()
    return await proxy_request(request, "/threads", method="POST")


@router.get("/threads/{thread_id}")
async def get_thread(request: Request, thread_id: str):
    """Get a conversation thread.

    Args:
        request: The incoming request
        thread_id: The thread ID

    Returns:
        Response: Thread data from LanGraph
    """
    await check_auth()
    return await proxy_request(request, f"/threads/{thread_id}", method="GET")


@router.get("/threads/{thread_id}/history")
async def get_thread_history(request: Request, thread_id: str):
    """Get the history of a conversation thread.

    Args:
        request: The incoming request
        thread_id: The thread ID

    Returns:
        Response: Thread history from LanGraph
    """
    await check_auth()
    return await proxy_request(request, f"/threads/{thread_id}/history", method="GET")
