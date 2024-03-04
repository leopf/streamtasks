import asyncio
from functools import wraps


def async_timeout(seconds):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Use asyncio.wait_for to apply a timeout to the function
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                # Handle the timeout error as needed
                print(f"Function {func.__name__} timed out after {seconds} seconds.")
                # Depending on your use case, you might want to return a value, raise an exception, etc.
                return None
        return wrapper
    return decorator