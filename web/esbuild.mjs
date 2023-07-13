import * as esbuild from "esbuild";
import http from "http";
import httpProxy from "http-proxy";

const ctx = await esbuild.context({
    entryPoints: ["src/index.tsx"],
    bundle: true,
    minify: true,
    sourcemap: true,
    define: {
        "process.env.NODE_ENV": '"development"',
    },
    target: ["es2015"],
    outfile: "dist/js/main.js",
})

const { port, host } = await ctx.serve({ servedir: "dist", })

const frontendServer = `http://${host}:${port}`;

http.createServer(async (req, res) => {
    const forwardRequest = (path) => {
        const options = {
            hostname: host,
            port,
            path,
            method: req.method,
            headers: req.headers,
        };

        const proxyReq = http.request(options, (proxyRes) => {
            if (proxyRes.statusCode === 404) {
                // If esbuild 404s the request, assume it's a route needing to
                // be handled by the JS bundle, so forward a second attempt to `/`.
                return forwardRequest("/");
            }

            // Otherwise esbuild handled it like a champ, so proxy the response back.
            res.writeHead(proxyRes.statusCode, proxyRes.headers);
            proxyRes.pipe(res, { end: true });
        });

        req.pipe(proxyReq, { end: true });
    };

    // When we're called pass the request right through to esbuild.
    forwardRequest(req.url);
}).listen(8001, host)
console.log(`Serving on http://${host}:${8001}`)