import deepEqual from "deep-equal";
import { TaskIO, Task, TaskOutput } from "../types/task";
import { InputConnection, Node, OutputConnection } from "./node-editor";
import { ManagedTask, extractTaskIO } from "./task";
import { EventEmitter } from "eventemitter3";

type TaskIOWithLabel = TaskIO & { label: string };

function extractIOWithLabel(task: Task): TaskIOWithLabel {
    return {
        label: task.label,
        ...extractTaskIO(task)
    }
}

function compareTaskIO( ignoreInputTopicId?: string) {
    
}

export class TaskNode extends EventEmitter<{ "updated": [] }> implements Node {
    private task: ManagedTask;

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
        return this.task.outputs.map(output => (<OutputConnection>{
            ...Object.fromEntries(Object.entries(output).filter(([k, v]) => k !== "topic_id")),
            id: output.topic_id,
            streamId: output.topic_id,
            label: typeof output.label === "string" ? output.label : undefined,
        }));
    }
    public get inputs(): InputConnection[] {
        return this.task.inputs.map(input => (<InputConnection>{
            ...Object.fromEntries(Object.entries(input).filter(([k, v]) => k !== "topic_id")),
            id: input.key,
            streamId: input.topic_id,
            key: input.key,
            label: typeof input.label === "string" ? input.label : undefined,
        }));
    }

    private updateHandlers: (() => void)[] = [];
    private lastTaskIO: TaskIOWithLabel;
    private inputKeyIgnoreTopicId?: string;

    constructor(task: ManagedTask) {
        super();
        this.task = task;
        this.lastTaskIO = extractIOWithLabel(task.storedInstance);
        this.task.on("updated", (newTask) => { // TODO: memory management
            const oldTaskIO = this.lastTaskIO;
            this.lastTaskIO = extractIOWithLabel(newTask);
            if (this.inputKeyIgnoreTopicId) {
                const oldInput = oldTaskIO.inputs.find(i => i.key === this.inputKeyIgnoreTopicId);
                const newInput = this.lastTaskIO.inputs.find(i => i.key === this.inputKeyIgnoreTopicId);
                if (oldInput) oldInput.topic_id = newInput?.topic_id;
            }
            if (!deepEqual(oldTaskIO, this.lastTaskIO)) {
                console.log("update!")
                this.emit("updated");
            }
        });
    }

    public async connect(key: string, output: OutputConnection | undefined) {
        let newOutput: undefined | TaskOutput;
        if (output) {
            newOutput = { ...output, topic_id: output.streamId };
            delete newOutput.id;
            delete newOutput.streamId;
        }
        try {
            this.inputKeyIgnoreTopicId = key;
            return await this.task.connect(key, newOutput)
        }
        catch (e) {
            this.inputKeyIgnoreTopicId = undefined;
            return String(e);
        }
    }
}