import { Node } from "./types";
import objectHash from "object-hash";

export function createNodeDisplayHash(node: Node) {
    const groups = node.getConnectionGroups();
    const name = node.getName();

    return objectHash({
        groups: groups.map(g => ({
            inputs: g.inputs.map(input => ({
                config: input.config,
                label: input.label,
            })),
            outputs: g.outputs.map(input => ({
                config: input.config,
                label: input.label,
            }))
        })),
        name
    })
}

export class Lock {
    private _locked = false;
    private _release_handlers: (() => void)[] = [];

    public async acquire() {
        if (this._locked) {
            await new Promise<void>(resolve => {
                this._release_handlers.push(resolve);
            });
        }
        this._locked = true;
    }
    public release() {
        if (this._release_handlers.length > 0) {
            const handler = this._release_handlers.shift();
            handler?.call(null);
        } 
        else {
            this._locked = false;
        }
    }
}