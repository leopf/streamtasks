import base64
import json
import pathlib
import tempfile
import unittest
import httpx
from streamtasks.asgiserver import ASGIRouter, ASGIServer, HTTPContext, decode_data_uri, http_context_handler, path_rewrite_handler, static_content_handler, static_files_handler
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

  async def test_rewrite(self):
    router = ASGIRouter()
    self.server.add_handler(router)

    @router.get("/base/{name*}")
    @path_rewrite_handler("/{name*}/hello")
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text(ctx.path)

    @router.get("/base2/{name*}")
    @path_rewrite_handler("/{name}/hello") # NOTE: if name has a slash, this will fail and raise a ValueError
    @http_context_handler
    async def _(ctx: HTTPContext):
      await ctx.respond_text(ctx.path)

    self.assertEqual((await self.client.get("/base/1337")).text, "/1337/hello")
    self.assertEqual((await self.client.get("/base/1337/2")).text, "/1337/2/hello")
    self.assertEqual((await self.client.get("/base2/1337")).text, "/1337/hello")
    self.assertEqual((await self.client.get("/base2/1337/2")).status_code, 500)

  async def test_static_files(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_dir = pathlib.Path(temp_dir)
      self.server.add_handler(static_files_handler(temp_dir, ["index.txt"], response_buffer_size=4))

      with open(temp_dir.joinpath("index.txt"), "w") as fd: fd.write("Test1")
      with open(temp_dir.joinpath("test.html"), "w") as fd: fd.write("<h1>Yo</h1>")

      index_res = await self.client.get("/")
      self.assertEqual(index_res.text, "Test1")
      self.assertTrue(index_res.headers.get("content-type", "").startswith("text/plain"))

      index_res = await self.client.get("/test.html")
      self.assertEqual(index_res.text, "<h1>Yo</h1>")
      self.assertTrue(index_res.headers.get("content-type", "").startswith("text/html"))

  async def test_static_content(self):
    data, mime_type, charset = decode_data_uri("data:text/plain;charset=UTF-8;base64," + base64.b64encode(b"Hello World").decode("ascii"))

    self.server.add_handler(static_content_handler(data, mime_type, charset))
    res = await self.client.get("/")
    self.assertTrue(res.headers.get("content-type", "").startswith("text/plain"))
    self.assertIn("utf-8", res.headers.get("content-type", ""))
    self.assertEqual(res.text, "Hello World")


if __name__ == '__main__':
  unittest.main()
