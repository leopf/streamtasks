import json
import unittest
import httpx
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, http_context_handler
from pydantic import BaseModel

class TestModel(BaseModel):
  test: str


class TestASGIServer(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self) -> None:
    self.server = ASGIServer()
    
    transport = httpx.ASGITransport(app=self.server)
    self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

  async def asyncTearDown(self) -> None:
    await self.client.aclose()
  
  async def test_simple_text(self):
    @self.server.handler
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text("Hello World!")
      
    res = await self.client.get("/test")
    self.assertEqual(res.text, "Hello World!")

  async def test_router(self):
    router = ASGIRouter()
    self.server.add_handler(router)
    
    @router.get("/test1")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text("Hello World!")
      
    @router.get("/test2/{name}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text(f"Hello {ctx.params.get('name', '')}!")
      
    @router.get("/test3/{name*}")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text(f"Hello World from {ctx.params.get('name', '')}!")
      
    @router.get("/test4/{name*}/yo")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text(f"Hello World from {ctx.params.get('name', '')}!")
      
    @router.get("/test5/")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.next()
      
    self.assertEqual((await self.client.get("/test1")).text, "Hello World!")
    self.assertEqual((await self.client.get("/test2/earth")).text, "Hello earth!")
    self.assertEqual((await self.client.get("/test3/earth/milkyway")).text, "Hello World from earth/milkyway!")
    self.assertEqual((await self.client.get("/test4/earth/andromeda/yo")).text, "Hello World from earth/andromeda!")
    self.assertEqual((await self.client.get("/test5/", headers={ "content-type": "application/json; charset=utf-8" })).status_code, 404)

  async def test_post_json(self):
    @self.server.handler
    @http_context_handler
    async def _(ctx: HTTPContext):
      model = TestModel.model_validate(await ctx.receive_json())
      await ctx.respond_json({ "yousent": model.test })
      
    res = await self.client.post("/", content=TestModel(test="win!").model_dump_json(), headers={ "content-type": "application/json" })
    self.assertEqual(json.loads(res.text)["yousent"], "win!")


if __name__ == '__main__':
  unittest.main()
