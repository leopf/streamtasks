import { TaskOutput } from "../types/task";
import { InputConnection, Node, OutputConnection } from "./node-editor";
import { ManagedTaskInstance, TaskConnectResult } from "./task";

export class TaskNode implements Node {
    private task: ManagedTaskInstance;

    public get id(): string {
        return this.task.id;
    }

    public get label(): string {
        return this.task.label;
    }
    public get position(): { x: number; y: number; } {
        return this.task.frontendConfig.position ?? { x: 0, y: 0 };
    }
    public set position(v) {
        this.task.frontendConfig.position = v;
    }

    public get outputs(): OutputConnection[] {
        return this.task.outputs.map(output => ({
            ...Object.fromEntries(Object.entries(output).filter(([k, v]) => k !== "topic_id")),
            id: output.topic_id,
            streamId: output.topic_id,
            label: typeof output.label === "string" ? output.label : undefined,
        }));
    }
    public get inputs(): InputConnection[] {
        return this.task.inputs.map(input => ({
            ...Object.fromEntries(Object.entries(input).filter(([k, v]) => k !== "topic_id")),
            id: input.key,
            streamId: input.topic_id,
            key: input.key,
            label: typeof input.label === "string" ? input.label : undefined,
        }));
    }

    private updateHandlers: (() => void)[] = [];

    constructor(task: ManagedTaskInstance) {
        this.task = task;
    }

    public async connect(key: string, output: OutputConnection | undefined) {
        let newOutput: undefined | TaskOutput;
        if (output) {
            newOutput = { ...output, topic_id: output.streamId };
            delete newOutput.id;
        }

        try {
            const res = await this.task.connect(key, newOutput)
            if (res === TaskConnectResult.successWithUpdate) {
                this.emitUpdate();
                return true;
            }
            else if (res === TaskConnectResult.success) {
                return true;
            }
            else {
                return false;
            }
        }
        catch (e) {
            return String(e);
        }
    }
    public onUpdated(hdl: () => void) {
        this.updateHandlers.push(hdl);
    }

    private emitUpdate() {
        this.updateHandlers.forEach(hdl => hdl.call(null))
    }
}