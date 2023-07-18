import * as esbuild from "esbuild";

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

await ctx.watch()
