import { Metadata, StoredTaskInstance, TaskConfigurator, TaskConfiguratorContext, TaskFrontendConfig, TaskIO, TaskInput, TaskInstance, TaskOutput } from "../types/task.ts"
import EventEmitter from "eventemitter3";
import cloneDeep from "clone-deep";
import deepEqual from "deep-equal";

const defaultRemapTopicIds = (taskInstance: TaskInstance, idMap: Map<number, number>, context: TaskConfiguratorContext) => {
    taskInstance.inputs.forEach(i => i.topic_id = i.topic_id ? idMap.get(i.topic_id) : undefined);
    taskInstance.outputs.forEach(o => o.topic_id = idMap.get(o.topic_id) ?? (() => { throw new Error("Missing output id in map.") })());
    return taskInstance;
};

export function extractTaskIO(taskInstance: TaskInstance): TaskIO {
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

export class ManagedTaskInstance extends EventEmitter<{"updated": [TaskInstance] }> {
    private readonly taskInstance: TaskInstance;
    private configurator: TaskConfigurator;
    private configuratorContext: TaskConfiguratorContext;

    public get id() {
        return this.taskInstance.id;
    }

    public get label() {
        return this.taskInstance.label;
    }

    public get inputs() {
        return this.taskInstance.inputs;
    }

    public get outputs() {
        return this.taskInstance.outputs;
    }

    private _frontendConfig: TaskFrontendConfig;
    public get frontendConfig(): TaskFrontendConfig {
        return this._frontendConfig;
    }

    public get storedInstance(): StoredTaskInstance {
        return {
            ...this.taskInstance,
            frontendConfig: this._frontendConfig
        };
    }

    public get hasEditor() {
        return this.configurator.renderEditor;
    }

    constructor(taskInstance: StoredTaskInstance, configurator: TaskConfigurator, configuratorContext: TaskConfiguratorContext) {
        super();
        this.taskInstance = taskInstance;
        this._frontendConfig = taskInstance.frontendConfig ?? {};
        this.configurator = configurator;
        this.configuratorContext = configuratorContext;
    }

    public updateData(taskInstance: StoredTaskInstance, overwriteStored: boolean = false) {
        Object.assign(this.taskInstance, taskInstance);
        if (overwriteStored) {
            this._frontendConfig = taskInstance.frontendConfig ?? {};
        }
        this.emit("updated", this.taskInstance);
    }

    public async getStartConfig() {
        return await this.configurator.toStartConfig?.call(null, this.taskInstance, this.configuratorContext) ?? this.taskInstance.config;
    }

    public async remapTopicIds(idMap: Map<number, number>) {
        const newData = await (this.configurator.remapTopicIds ?? defaultRemapTopicIds).call(null, this.taskInstance, idMap, this.configuratorContext);
        this.updateData(newData);
    }

    public async connect(key: string, output?: TaskOutput): Promise<boolean> {
        const oldInstanceClone = cloneDeep(this.taskInstance);
        const newInstance = await this.configurator.connect(this.taskInstance, key, output, this.configuratorContext);
        
        if (!deepEqual(newInstance, oldInstanceClone)) {
            this.updateData(newInstance);
        }
        return this.taskInstance.inputs.find(input => input.key === key)?.topic_id === output?.topic_id;
    }

    public renderEditor(element: HTMLElement) {
        if (!this.configurator.renderEditor) {
            return;
        }
        this.configurator.renderEditor(this.taskInstance, element, this.configuratorContext);
    }
}


export function getErrorConfigurator(error: unknown): TaskConfigurator {
    const errorFn = () => { throw error };
    return {
        connect: errorFn,
        create: errorFn,
    };
} 