import asyncio
from functools import wraps
import os
import unittest


def async_timeout(seconds):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs): return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
        return wrapper
    return decorator

def full_test(o): return o #return unittest.skipIf(not bool(os.getenv("FULL")), "Disabled for performance reasons. Use env FULL=1 to enable.")(o)