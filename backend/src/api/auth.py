"""Authentication utilities for API key validation."""

import httpx


async def validate_anthropic_api_key(api_key: str) -> tuple[bool, str]:
    """Validate an Anthropic API key by making a test request.

    Args:
        api_key: The API key to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not api_key or len(api_key.strip()) == 0:
        return False, "API key cannot be empty"

    # Basic format validation
    if not api_key.startswith("sk-ant-"):
        return False, "Invalid API key format. Key should start with 'sk-ant-'"

    # Test the API key with a minimal request
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-7-sonnet-latest",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "test"}],
                },
            )

            if response.status_code == 200:
                return True, "API key is valid"
            elif response.status_code == 401:
                return False, "Invalid API key"
            elif response.status_code == 429:
                # Rate limited, but key is valid
                return True, "API key is valid (rate limited)"
            elif response.status_code == 404:
                # Model not found, but API key is likely valid
                # Try with a different model
                response2 = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-7-sonnet-latest",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "test"}],
                    },
                )
                if response2.status_code == 200:
                    return True, "API key is valid"
                elif response2.status_code == 401:
                    return False, "Invalid API key"
                else:
                    return (
                        False,
                        f"Validation failed with status {response2.status_code}",
                    )
            else:
                return (
                    False,
                    f"Validation failed with status {response.status_code}",
                )

    except httpx.TimeoutException:
        return False, "Request timed out while validating API key"
    except httpx.RequestError as e:
        return False, f"Network error during validation: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during validation: {str(e)}"
