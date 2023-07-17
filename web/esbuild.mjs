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

const attemptPorts = [ 8010, frontendPort ];

http.createServer((req, res) => {
    let portIndex = 0;
    const forwardRequest = (port, path) => {
        const options = {
            hostname: host,
            port,
            path,
            method: req.method,
            headers: req.headers,
        };
        let done = false;
        const callNext = () => {
            if (done) return;
            done = true;
            portIndex += 1;
            if (portIndex < attemptPorts.length) {
                return forwardRequest(attemptPorts[portIndex], path);
            }
            else {
                return forwardRequest(frontendPort, "/");
            }
        };

        const proxyReq = http.request(options, (proxyRes) => {
            if (done) return;
            
            if (proxyRes.statusCode === 404) {
                callNext();
                return;
            }
            res.writeHead(proxyRes.statusCode, proxyRes.headers);
            proxyRes.pipe(res, { end: true });
        });

        proxyReq.on("error", (e) => {
            callNext();
        });

        req.pipe(proxyReq, { end: true });
    };

    try {
        forwardRequest(attemptPorts[portIndex], req.url);
    }
    catch (e) {
        console.error(e);
        res.writeHead(500);
        res.end("Internal Server Error");
    }
}).listen(8001, host)
console.log(`Serving on http://${host}:${8001}`)