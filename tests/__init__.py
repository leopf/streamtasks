import os
import asyncio

timeout = len(os.environ["TIMEOUT"]) if "TIMEOUT" in os.environ else 1 

async def atimeoutfn(timeout=timeout):
  def wrap(func):
    async def wrapped(*args, **kwargs):
      return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
    return wrapped
  return wrap