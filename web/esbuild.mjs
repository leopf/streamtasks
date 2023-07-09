import * as esbuild from "esbuild";
import http from "http";
import httpProxy from "http-proxy";

const ctx = await esbuild.context({
    entryPoints: ["src/index.ts"],
    bundle: true,
    minify: true,
    sourcemap: true,
    target: ["es2015"],
    outfile: "dist/js/main.js",
})

const { port, host } = await ctx.serve({ servedir: "dist" })

let backendServers = [ "http://localhost:" + port ]

const proxy = httpProxy.createProxyServer({
    changeOrigin: true
});

http.createServer(async (req, res) => {
    let serverIndex = 0;
    function proxyRequest() {
        proxy.web(req, res, { target: backendServers[serverIndex] }, (err) => {
            serverIndex++;
            if (serverIndex < backendServers.length) {
                proxyRequest();
            }
            else {
                // send 404
                res.writeHead(404, { "Content-Type": "text/plain" });
                res.end("Not found");
            }
        });
    }

    proxyRequest();
}).listen(8001, host)
console.log(`Serving on http://${host}:${8001}`)