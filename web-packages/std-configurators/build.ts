import esbuild from "esbuild";
import fs from "fs";
import path from "path";

const entriesDir = "src/entries";
const ctx = await esbuild.context({
    outdir: "../../streamtasks/system/assets/public/configurators/",
    entryPoints: (await fs.promises.readdir(entriesDir)).map(fn => path.resolve(entriesDir, fn)),
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

