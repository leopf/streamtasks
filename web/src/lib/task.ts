import { Metadata, TaskConfigurator, TaskConfiguratorContext, TaskFrontendConfig, TaskIO, TaskInput, Task, TaskOutput, FullTask, TaskInstanceStatus } from "../types/task.ts"
import EventEmitter from "eventemitter3";
import cloneDeep from "clone-deep";
import deepEqual from "deep-equal";
import { TaskModel } from "../model/task.ts";
import { GeneralStatus } from "../types/status.ts";

export function extractTaskIO(taskInstance: Task): TaskIO {
    return {
        inputs: taskInstance.inputs.map(input => ({ ...input })),
        outputs: taskInstance.outputs.map(output => ({ ...output }))
    }
}

export function validateMetadataEquals(a: Metadata, b: Metadata, ignoreFields: Set<keyof TaskInput>) {
    for (const metadataKey of new Set([...Object.keys(a), ...Object.keys(b)].filter(k => !ignoreFields.has(k)))) {
        if (a[metadataKey] !== b[metadataKey]) {
            throw new Error(`Metadata mismatch on field "${metadataKey}".`);
        }
    }
}

export const ignoreIOFieldsInEquality = ["label"];
export const taskHostLabelFields = ["label", "cfg:label"];
export const taskHostDescriptionFields = ["description", "cfg:description"];
export const ioMetadataKeyLabels: Record<string, string> = { "topic_id": "topic id" }
export const ioMetadataValueLabels: Record<string, Record<string, string>> = { "type": { "ts": "timestamp" } }
export const ioMetadataHideKeys = new Set([ "key" ]);

export const taskInstance2GeneralStatusMap: Record<TaskInstanceStatus, GeneralStatus> = {
    ended: "passive",
    failed: "error",
    stopped: "passive",
    scheduled: "passive",
    running: "ok",
};

export class ManagedTask extends EventEmitter<{"updated": [FullTask] }> {
    private readonly _task: FullTask;
    private configurator: TaskConfigurator;
    private configuratorContext: TaskConfiguratorContext;

    public get id() {
        return this._task.id;
    }

    public get label() {
        return this._task.label;
    }

    public get inputs() {
        return this._task.inputs;
    }

    public get outputs() {
        return this._task.outputs;
    }

    public get frontend_config(): TaskFrontendConfig {
        return this._task.frontend_config;
    }

    public get taskInstance() {
        return this._task.task_instance;
    }

    public get task(): FullTask {
        return { ...this._task };
    }

    public get hasEditor() {
        return this.configurator.renderEditor;
    }

    constructor(task: Task & Partial<FullTask>, configurator: TaskConfigurator, configuratorContext: TaskConfiguratorContext) {
        super();
        this._task = {
            ...task,
            frontend_config: task.frontend_config ?? {},
        };
        this.configurator = configurator;
        this.configuratorContext = configuratorContext;
    }

    public updateData(taskInstance: Partial<FullTask>) {
        Object.assign(this._task, taskInstance);
        this.emit("updated", this._task);
    }
    
    public async connect(key: string, output?: TaskOutput): Promise<boolean> {
        const oldInstanceClone = cloneDeep(TaskModel.parse(this._task));
        const newInstance: Task = TaskModel.parse(await this.configurator.connect(this._task, key, output, this.configuratorContext));
        
        if (!deepEqual(newInstance, oldInstanceClone)) {
            this.updateData(newInstance);
        }
        return this._task.inputs.find(input => input.key === key)?.topic_id === output?.topic_id;
    }

    public renderEditor(element: HTMLElement) {
        if (!this.configurator.renderEditor) {
            return;
        }
        this.configurator.renderEditor(this._task, element, this.configuratorContext);
    }
}


export function getErrorConfigurator(error: unknown): TaskConfigurator {
    const errorFn = () => { throw error };
    return {
        connect: errorFn,
        create: errorFn,
    };
} 