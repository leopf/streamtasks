import deepEqual from "deep-equal";
import { EventEmitter } from "eventemitter3";
import _ from "underscore";
import { InputConnection, OutputConnection, Node } from "./node-editor";
import { TaskIO, TaskInstanceStatus, FullTask, extractTaskIO, ManagedTask, TaskOutput } from "@streamtasks/core";
import { GeneralStatus } from "../types/status";
import { generalStatusColors } from "./status";
import { taskInstance2GeneralStatusMap } from "./task";

type TaskNodeData = TaskIO & { label: string, status?: TaskInstanceStatus };

function extractNodeData(task: FullTask): TaskNodeData {
    return {
        label: task.label,
        status: task.task_instance?.status,
        ...extractTaskIO(task)
    }
}

const taskGeneralStatusColors: Record<GeneralStatus, string | undefined> = {
    ...generalStatusColors,
    ok: undefined
}

export class TaskNode extends EventEmitter<{ "updated": [] }> implements Node {
    private task: ManagedTask;

    public get id(): string {
        return this.task.id;
    }

    public get host() {
        return this.task.parsedTaskHost.nodeName;
    }

    public get outlineColor() {
        let status: GeneralStatus = "ok";
        if (this.task.taskHost.metadata["js:configurator"] === "std:notfound") {
            status = "error";
        }
        else if (this.task.taskInstance) {
            status = taskInstance2GeneralStatusMap[this.task.taskInstance.status];
        }
        return taskGeneralStatusColors[status];
    }

    public get label(): string {
        const originalLabel = this.task.parsedTaskHost.label;
        if (this.task.label.includes(originalLabel)) {
            return this.task.label;
        }
        else {
            return `${originalLabel}: ${this.task.label}`
        }
    }
    public get position(): { x: number; y: number; } {
        return this.task.frontend_config.position ?? { x: 0, y: 0 };
    }
    public set position(v) {
        this.task.frontend_config.position = v;
        this.onPositionUpdate();
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

    private lastData: TaskNodeData;
    private inputKeyIgnoreTopicId?: string;
    private disposers: (() => void)[] = [];
    private onTaskUpdated = (newTask: FullTask) => {
        const oldTaskIO = this.lastData;
        this.lastData = extractNodeData(newTask);
        if (this.inputKeyIgnoreTopicId) {
            const oldInput = oldTaskIO.inputs.find(i => i.key === this.inputKeyIgnoreTopicId);
            const newInput = this.lastData.inputs.find(i => i.key === this.inputKeyIgnoreTopicId);
            if (oldInput) oldInput.topic_id = newInput?.topic_id;
        }
        if (!deepEqual(oldTaskIO, this.lastData)) {
            this.emit("updated");
        }
    }
    private onPositionUpdate = _.debounce(() => this.task.updateData({}), 500);

    constructor(task: ManagedTask) {
        super();
        this.task = task;
        this.lastData = extractNodeData(task.task);

        this.task.on("updated", this.onTaskUpdated);
        this.disposers.push(() => this.task.off("updated", this.onTaskUpdated));
    }

    public destroy() {
        this.disposers.forEach(d => d());
        this.removeAllListeners();
    }

    public async connect(key: string, output: OutputConnection | undefined) {
        let newOutput: undefined | TaskOutput;
        if (output) {
            newOutput = { ...output, topic_id: output.streamId };
            delete newOutput!.id;
            delete newOutput!.streamId;
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