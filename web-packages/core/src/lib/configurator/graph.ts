import objectPath from "object-path";

export function matchBasePath(path: string, basePath: string) {
    if (path === basePath) {
        return "";
    }
    else if (path.startsWith(basePath + ".")) {
        return path.substring(basePath.length + 1);
    }
    else {
        return undefined;
    }
}

export function getAllObjectPaths(obj: any, basePath: string = ""): string[] {
    if (typeof obj === "object" && obj !== null) {
        if (Array.isArray(obj)) {
            return obj.map((el, idx) => getAllObjectPaths(el, basePath ? `${basePath}.${idx}` : `${idx}`)).reduce((pv, cv) => [...pv, ...cv], []);
        }
        else {
            return Object.entries(obj).map(([k, v]) => getAllObjectPaths(v, basePath ? `${basePath}.${k}` : `${k}`)).reduce((pv, cv) => [...pv, ...cv], []);
        }
    }
    return [basePath];
}

export class GraphSetter<T extends object> {
    private edgeGenerators: [string, (subPath: string) => string[]][] = [];
    private validators: [string, (v: any, subPath: string) => boolean][] = [];
    private setters = new Map<string, any>();

    public data: T;

    constructor(data: T) {
        this.data = data;
    }

    public addEdge(path1: string, path2: string) {
        this.edgeGenerators.push([path1, () => [path2]]);
        this.edgeGenerators.push([path2, () => [path1]]);
    }
    public addEdgeGenerator(basePath: string, gen: (subPath: string) => string[]) {
        this.edgeGenerators.push([basePath, gen]);
    }
    public addValidator(path: string, validator: (v: any, subPath: string) => boolean) {
        this.validators.push([path, validator]);
    }

    public isDisabled(path: string) {
        for (const p of this.getEffectedPaths(path)) {
            const value = objectPath.get(this.data, p);
            if (!this.validatePathValue(p, value)) {
                return true;
            }
        }
        return false;
    }
    public getDisabledPaths(root: string, strip: boolean) { // TODO: make this more efficient
        const disabledPaths = new Set<string>();
        const data = objectPath.get(this.data, root);
        const paths = getAllObjectPaths(data, root);
        let rootLen = root.endsWith(".") ? root.length : root.length + 1
        for (const p of paths) {
            if (this.isDisabled(p)) {
                if (strip) {
                    disabledPaths.add(p.substring(rootLen));
                }
                else {
                    disabledPaths.add(p);
                }
            }
        }
        return disabledPaths;
    }

    public apply() {
        const model = objectPath(this.data);
        const setters: [string, any][] = []
        for (const [path, value] of this.setters.entries()) {
            if (model.get(path) !== value) {
                if (!this.validatePathValue(path, value)) {
                    throw new Error(`Invalid value on path "${path}"!`);
                }
                setters.push([path, value])
            }
        }
        for (const [path, value] of setters) {
            model.set(path, value);
        }
    }

    public set(path: string, value: any) {
        for (const p of this.getEffectedPaths(path)) {
            this.setters.set(p, value);
        }
    }
    public reset() {
        this.setters.clear();
    }


    private validatePathValue(path: string, value: any) {
        for (const [basePath, validator] of this.validators) {
            const subPath = matchBasePath(path, basePath);
            if (subPath !== undefined && !validator(value, subPath)) {
                return false;
            }
        }
        return true;
    }
    private getEffectedPaths(path: string) {
        const visitedPaths = new Set([path]);
        const newPaths = new Set([path]);
        while (newPaths.size > 0) {
            const visitPaths = Array.from(newPaths);
            newPaths.clear();
            for (const path of visitPaths) {
                const paths = this.getConnectedNodes(path);
                for (const npath of paths) {
                    if (!visitedPaths.has(npath)) {
                        newPaths.add(npath);
                        visitedPaths.add(npath);
                    }
                }
            }
        }
        return visitedPaths;
    }
    private getConnectedNodes(path: string) {
        const nodes: string[] = [];
        for (const [basePath, gen] of this.edgeGenerators) {
            const subPath = matchBasePath(path, basePath)
            if (subPath !== undefined) {
                nodes.push(...gen(subPath));
            }
        }
        return nodes;
    }
}