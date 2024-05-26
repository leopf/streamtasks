import esbuild from "esbuild";


const ctx = await esbuild.context({
    outdir: "../../streamtasks/system/assets/public/configurators/",
    entryPoints: [ "src/static.tsx", "src/multitrackio.tsx", "src/notfound.ts" ],
    bundle: true,
    platform: "browser",
    sourcemap: "inline",
    minify: true,
    format: "esm"
})

await ctx.rebuild()
if (process.argv.at(-1) === "--watch") {
    console.log("watching...")
    await ctx.watch()
}
else {
    await ctx.dispose()
}

