
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
    private disableCheckers: [string, (subPath: string, basePath: string) => boolean][] = [];
    
    private edges = new Map<string, string[]>();
    private edgeGenerators: [string, (subPath: string, basePath: string) => string[]][] = [];

    private setters = new Map<string, any>();

    public constrainValidator(path: string, validator: (v: any) => boolean) {
        this.validatorsConstraints[path] = validator;
    }
    public constrainValue(path: string, value: any) {
        this.valueConstraints[path] = value;
    }

    public addDisableCheck(basePath: string, gen: (subPath: string, basePath: string) => boolean) {
        this.disableCheckers.push([basePath, gen]);
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
                throw new Error(`Setter has a value conflict on path "${p}" between "${value}" and "${this.setters.get(p)}"`);
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
            if (this.checkPathDisabled(p)) {
                return true;
            }
        }
        return false;
    }

    public validate(): Record<string, any> {
        const result: Record<string, any> = {};
        for (const [setField, setValue] of this.setters.entries()) {
            if (this.checkPathDisabled(setField)) {
                throw new Error(`Trying to set path "${setField}" which is disabled!`);
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

    private checkPathDisabled(path: string) {
        for (const [basePath, checker] of this.disableCheckers) {
            const subPath = matchBasePath(path, basePath)
            if (subPath !== undefined && checker(subPath, basePath)) {
                return true;
            }
        }
        return false;
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