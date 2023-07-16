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

const { port: frontendPort, host } = await ctx.serve({ servedir: "dist", })

const attemptPorts = [ frontendPort, 8010 ];

http.createServer(async (req, res) => {
    let portIndex = 0;
    const forwardRequest = (port, path) => {
        const options = {
            hostname: host,
            port,
            path,
            method: req.method,
            headers: req.headers,
        };

        const proxyReq = http.request(options, (proxyRes) => {
            if (proxyRes.statusCode === 404) {
                portIndex += 1;
                if (portIndex < attemptPorts.length) {
                    return forwardRequest(attemptPorts[portIndex], path);
                }
                else {
                    return forwardRequest(port, "/");
                }
            }

            // Otherwise esbuild handled it like a champ, so proxy the response back.
            res.writeHead(proxyRes.statusCode, proxyRes.headers);
            proxyRes.pipe(res, { end: true });
        });

        req.pipe(proxyReq, { end: true });
    };

    // When we're called pass the request right through to esbuild.
    forwardRequest(attemptPorts[portIndex], req.url);
}).listen(8001, host)
console.log(`Serving on http://${host}:${8001}`)