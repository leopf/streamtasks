import * as esbuild from "esbuild";
import http from "http";
import httpProxy from "http-proxy";

const ctx = await esbuild.context({
    entryPoints: ["src/index.tsx"],
    bundle: true,
    minify: true,
    sourcemap: true,
    target: ["es2015"],
    outfile: "dist/js/main.js",
})

const { port, host } = await ctx.serve({ servedir: "dist",  })

const frontendServer = `http://${host}:${port}`; 
const backendServers = [ frontendServer ]

const proxy = httpProxy.createProxyServer({
    changeOrigin: true
});

http.createServer(async (req, res) => {
    let serverIndex = 0;
    function proxyRequest() {
        proxy.web(req, res, { target: backendServers[serverIndex],  }, (err) => {
            serverIndex++;
            if (serverIndex < backendServers.length) {
                proxyRequest();
            }
            else {
                console.log("hi")
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Something went wrong. And we are reporting a custom error message.');
                // // send request "/" to frontend server
                // proxy.web(req, res, { target: frontendServer, ignorePath: true, prependPath: false });
            }
        });
    }

    proxyRequest();
}).listen(8001, host)
console.log(`Serving on http://${host}:${8001}`)