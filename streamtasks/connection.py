import asyncio
import struct
from streamtasks.net import ConnectionClosedError, Link
from streamtasks.net.message.serialize import deserialize_message, serialize_message
from streamtasks.net.message.types import Message

SYNC_WORD = b"\xb8\x23\xa0\x6f"

class StreamLink(Link):
  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cost: int):
    super().__init__(cost)
    self._reader = reader
    self._writer = writer
    
  async def _send(self, message: Message):
    try: await asyncio.shield(self._write_message(message)) # prevent out of sync issues
    except asyncio.CancelledError: raise
    except: raise ConnectionClosedError()

  async def _recv(self) -> Message:
    try: await asyncio.shield(self._read_message()) # prevent out of sync issues
    except asyncio.CancelledError: raise
    except: raise ConnectionClosedError()
    
  async def _write_message(self, message: Message):
    data = serialize_message(message)
    await self._writer.write(SYNC_WORD)
    await self._writer.write(struct.pack("<L", len(data)))
    await self._writer.write(data)
    await self._writer.drain()
    
  async def _read_message(self): # TODO optimize
    sync_index = 0
    while sync_index < len(SYNC_WORD):
      next_byte = await self._reader.read(1)
      if SYNC_WORD[sync_index] == next_byte[0]: sync_index += 1
      else: sync_index = 0
    data_len_raw = await self._reader.read(4)
    data_len = struct.unpack("<L", data_len_raw)
    return deserialize_message(await self._reader.read(data_len))
      
async def connect_tcp(host: str, port: int, cost: int):
  reader, writer = await asyncio.open_connection(host, port)
  
  return StreamLink(reader, writer, cost)