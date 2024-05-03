import { z } from "zod";
import { Metadata } from "../../types/task";

export const compareIgnoreMetadataKeys = new Set(["key", "topic_id", "label"]);

export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: true): O;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: false): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force?: boolean) {
    let rawData: any = metadata[key]
    try {
        rawData = JSON.parse(String(rawData));
    }  
    catch {}
    if (rawData === undefined) {
        if (force) {
            throw new Error(`Field "${key}" not defined!`);
        }
        return undefined;
    }
    if (force) {
        return model.parse(rawData)
    }
    else {
        const res = model.safeParse(rawData);
        if (res.success) {
            return res.data;
        }
        return undefined;
    }
}

export function extractObjectPathValues(data: any, prefix: string = "", result?: Map<string, any>) {
    result = result ?? new Map();
    // TODO: fix recursion
    if (typeof data == "object") {
        if (Array.isArray(data)) {
            data.forEach((v, idx) => extractObjectPathValues(v, prefix + idx + ".", result));
        }
        else {
            Object.entries(data).forEach(([k, v]) => extractObjectPathValues(v, prefix + k + ".", result))
        }
    }
    else {
        result.set(prefix.substring(0, prefix.length - 1), data);
    }
    return result;
}

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

export class GraphSetter {
    private validatorsConstraints: Record<string, (v: any) => boolean> = {};
    private valueConstraints: Record<string, any> = {};
    private disabledPaths = new Set<string>();
    
    private edges = new Map<string, string[]>();
    private edgeGenerators: [string, (subPath: string, basePath: string) => string[]][] = [];

    private setters = new Map<string, any>();

    public constrainValidator(path: string, validator: (v: any) => boolean) {
        this.validatorsConstraints[path] = validator;
    }
    public constrainValue(path: string, value: any) {
        this.valueConstraints[path] = value;
    }

    public disable(path: string) {
        this.disabledPaths.add(path);
    }

    public enable(path: string, deep: boolean = false) {
        this.disabledPaths.delete(path);
        if (deep) {
            Array.from(this.disabledPaths).forEach(dpath => {
                if (matchBasePath(dpath, path) !== undefined) {
                    this.disabledPaths.delete(dpath);
                }
            })
        }
    }

    public clearSetters() {
        this.setters.clear();
    }

    public addEdge(path1: string, path2: string) {
        this.edges.set(path1, [...(this.edges.get(path1) ?? []), path2]);
        this.edges.set(path2, [...(this.edges.get(path2) ?? []), path1]);
    }
    public addEdgeGenerator(basePath: string, gen: (subPath: string, basePath: string) => string[]) {
        this.edgeGenerators.push([basePath, gen]);
    }

    public set(path: string, value: any) {
        const paths = this.getEffectedPaths(path);
        for (const p of paths) {
            if (!this.setters.has(p)) {
                this.setters.set(p, value);
            }
            else if (this.setters.get(p) !== value) {
                throw new Error("Setter has a value conflict on path " + p);
            }
        }
    }

    // TODO: remove?
    public getDisabledFields(path: string, strip: boolean = true) {
        if (path.length > 0) {
            path += ".";
        }
        const paths = new Set([
            ...Object.keys(this.valueConstraints),
            ...Object.keys(this.validatorsConstraints),
            ...Object.keys(this.edges),
        ].filter(p => p.startsWith(path)));
        const result = new Set<string>();
        const substringStart = (strip && path.length > 0) ? path.length : 0; 
        for (const p of paths) {
            if (this.isDisabled(p)) {
                result.add(p.substring(substringStart));
            }
        }
        return result;
    }

    public isDisabled(path: string): boolean {
        const paths = this.getEffectedPaths(path);
        for (const p of paths) {
            if (p in this.valueConstraints) {
                return true;
            }
            for (const disabledPath of this.disabledPaths) {
                if (p.startsWith(disabledPath)) {
                    return true;
                }
            }
        }
        return false;
    }

    public validate(): Record<string, any> {
        const result: Record<string, any> = {};
        for (const [setField, setValue] of this.setters.entries()) {
            // check if any setters are disabled
            for (const disabledPath of this.disabledPaths) {
                if (setField.startsWith(disabledPath)) {
                    throw new Error(`Trying to set path "${setField}" which is in the disabled path "${disabledPath}"!`);
                }
            }
            const validatorConstraint = this.validatorsConstraints[setField];
            if (validatorConstraint && !validatorConstraint(setValue)) {
                throw new Error(`Validation for path "${setField}" failed!`);
            }

            const valueConstraint = this.valueConstraints[setField];
            if (valueConstraint !== undefined && valueConstraint !== setValue) {
                throw new Error(`Validation for path "${setField}" failed!`);
            }
            result[setField] = setValue;
        }
        return result;
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
        const nodes = Array.from(this.edges.get(path) ?? []);
        for (const [basePath, gen] of this.edgeGenerators) {
            const subPath = matchBasePath(path, basePath)
            if (subPath !== undefined) {
                nodes.push(...gen(subPath, basePath));
            }
        }
        return nodes;
    }
}