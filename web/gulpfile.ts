import esbuild from "esbuild";
import path from "path";
import { parallel, watch } from "gulp";
import { glob } from "glob";
import fsExtra from "fs-extra";

const outDir = "dist";
const dev = !!process.env.DEV;

const buildConfigurator = async (filename: string, out: string = ".") => {
    const outFilename = path.join(outDir, out, path.basename(filename).split(".", 2)[0] + ".js");
    await esbuild.build({
        entryPoints: [filename],
        bundle: true,
        outfile: outFilename,
        format: "esm",
        sourcemap: dev ? "inline" : false,
        minify: !dev,
        treeShaking: !dev
    });
}

const buildStdConfigurators = async () => {
    for (const fn of await glob("src/configurators/std/*")) {
        await buildConfigurator(fn, "configurators")
    }
}

const movePublic = async () => {
    for (const fn of await glob("public/**", { nodir: true })) {
        await fsExtra.copy(fn, path.join("dist/", path.relative("public/", fn)))
    }
}

const appBuildConfig: esbuild.SameShape<esbuild.BuildOptions, esbuild.BuildOptions> = {
    entryPoints: ["src/ui/index.tsx"],
    bundle: true,
    outfile: "dist/main.js",
    sourcemap: dev ? "inline" : false,
    minify: !dev,
    treeShaking: !dev
};

export const buildAll = parallel(
    buildStdConfigurators,
    movePublic,
    async () => await esbuild.build(appBuildConfig)
);
export const watchAll = parallel(
    () => watch("public/**", movePublic),
    () => watch("src/configurators/std/*", buildStdConfigurators),
    async () => await (await esbuild.context(appBuildConfig)).watch(),
);
