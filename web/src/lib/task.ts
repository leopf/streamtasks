import { StoredTaskInstance, TaskInstanceFrontendConfig } from "../types/task-frontend.ts";
import { TaskConfigurator, TaskConfiguratorContext, TaskHost, TaskInstance, TaskOutput } from "../types/task.ts"

const defaultRemapTopicIds = (taskInstance: TaskInstance, idMap: Map<number, number>, context: TaskConfiguratorContext) => {
    taskInstance.inputs.forEach(i => i.topic_id = i.topic_id ? idMap.get(i.topic_id) : undefined);
    taskInstance.outputs.forEach(o => o.topic_id = idMap.get(o.topic_id) ?? (() => { throw new Error("Missing output id in map.") })());
    return taskInstance;
};

export const ignoreIOFieldsInEquality = [ "label" ];

export class ManagedTaskInstance {
    private taskInstance: TaskInstance;
    private configurator: TaskConfigurator;
    private configuratorContext: TaskConfiguratorContext;
    
    private renderedEditorContainers: Set<HTMLElement> = new Set();
    private onTaskInstanceUpdatedListener = this.onTaskInstanceUpdated.bind(this);

    private _frontendConfig : TaskInstanceFrontendConfig = {};
    public get frontendConfig() : TaskInstanceFrontendConfig {
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

    constructor(taskInstance: TaskInstance, configurator: TaskConfigurator, configuratorContext: TaskConfiguratorContext) {
        this.taskInstance = taskInstance
        this.configurator = configurator
        this.configuratorContext = configuratorContext;    
    }

    public async getStartConfig() {
        return await this.configurator.toStartConfig?.call(null, this.taskInstance, this.configuratorContext) ?? this.taskInstance.config;
    }

    public async remapTopicIds(idMap: Map<number, number>) {
        this.taskInstance = await (this.configurator.remapTopicIds ?? defaultRemapTopicIds).call(null, this.taskInstance, idMap, this.configuratorContext);
    }

    public async connect(key: string, output: TaskOutput) {
        this.taskInstance = await this.configurator.connect(this.taskInstance, key, output, this.configuratorContext);
    }

    public renderEditor(element: HTMLElement) {
        if (!this.configurator.renderEditor) {
            return;
        }
        this.renderedEditorContainers.add(element);
        element.addEventListener("task-instance-updated", this.onTaskInstanceUpdatedListener);
        this.configurator.renderEditor(this.taskInstance, element, this.configuratorContext);
    }
    public unmountEditor(element: HTMLElement) {
        element.removeEventListener("task-instance-updated", this.onTaskInstanceUpdatedListener);
        this.renderedEditorContainers.delete(element);
    }

    private onTaskInstanceUpdated(e: Event) {
        if (e instanceof CustomEvent && "id" in e.detail && e.detail.id === this.taskInstance.id) {
            this.taskInstance = e.detail; // TODO: maybe it makes sense to do validation here
            this.handleTaskInstanceUpdated();
        }
    }
    private handleTaskInstanceUpdated() {
        if (!this.configurator.renderEditor) {
            return;
        }
        for (const container of this.renderedEditorContainers) {
            this.configurator.renderEditor(this.taskInstance, container, this.configuratorContext);
        }
    }
}

export class TaskManager {
    private configurators: Map<string, TaskConfigurator> = new Map();
    private idCounter: number = 1;

    // NOTE: do we want this???
    public async createTaskInstance(taskHost: TaskHost) {
        const configurator = await this.getConfigurator(taskHost);
        return await configurator.create(this.createContext(taskHost));
    }
    public async createManagedTaskInstance(taskHost:TaskHost) {
        const configurator = await this.getConfigurator(taskHost);
        const context = this.createContext(taskHost);
        const inst = await configurator.create(context);
        return new ManagedTaskInstance(inst, configurator, context);
    }

    private async getConfigurator(taskHost: TaskHost): Promise<TaskConfigurator> {
        if (!this.configurators.has(taskHost.id)) {
            let importUrl: string;
            if ("js:configurator" in taskHost.metadata) {
                const configuratorJs = taskHost.metadata["js:configurator"];
                if (typeof configuratorJs !== "string") {
                    throw new Error("Expected js:configurator to be a string.");
                }
                if (configuratorJs.startsWith("std:")) {
                    const stdConfiguratorName = configuratorJs.substring(4);
                    if (!/^[0-9a-z\-]+$/ig.test(stdConfiguratorName)) {
                        throw new Error("Invalid std configurator name!");
                    }
                    // TODO: stabalize this; make it agnostig to the host path?
                    importUrl = `/configurators/${stdConfiguratorName}.js`
                }
                else {
                    importUrl = URL.createObjectURL(new Blob([configuratorJs], { type: 'text/javascript' }));
                }
            }
            else {
                // TODO: stabalize this; make it agnostig to the host path?
                importUrl = `/task-host/${taskHost.id}/configurator.js`;
            }

            try {
                const configurator: TaskConfigurator = await import(importUrl);
                this.configurators.set(taskHost.id, configurator);
                return configurator;
            }
            catch {
                throw new Error("Failed to import configurator from default path.");
            }
            finally {
                URL.revokeObjectURL(importUrl); // in case of a blob url!
            }
        }
        else {
            return this.configurators.get(taskHost.id)!;
        }
    }

    private createContext(taskHost: TaskHost): TaskConfiguratorContext {
        return {
            taskHost: taskHost,
            idGenerator: () => this.idCounter++
        };
    }
}
