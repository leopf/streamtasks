import { TaskHost, TaskConfigurator, TaskHostModel, FullTask, getErrorConfigurator, ManagedTask, TaskConfiguratorContext } from "@streamtasks/core";
import { action, makeObservable, observable } from "mobx";
import { z } from "zod";

function getNotFoundTaskHost(id: string): TaskHost {
    return {
        id,
        metadata: {
            "label": "not found",
            "description": "The task host for this task was not found. Perhaps you have changed the name of a node, or you may be disconnected from a node.",
            "js:configurator": "std:notfound"
        }
    };
}

export class TaskManager {
    public taskHosts: Map<string, TaskHost> = observable.map();
    private configurators: Map<string, TaskConfigurator> = new Map();
    private idCounter: number = 1;

    constructor() {
        makeObservable(this, {
            loadTaskHosts: action,
        })
    }

    public async loadTaskHosts() {
        const result = await fetch("./api/task-hosts").then(res => res.json())
        z.array(TaskHostModel).parse(result).forEach(th => this.taskHosts.set(th.id, th));
    }

    public async toManagedTask(task: FullTask, fail: boolean = true) {
        let configurator: TaskConfigurator;
        let taskHost: TaskHost;
        try {
            taskHost = await this.getTaskHost(task.task_host_id);
            configurator = await this.getConfigurator(taskHost);
        }
        catch (e) {
            if (fail) throw e;
            taskHost = { id: task.task_host_id, metadata: {} };
            configurator = getErrorConfigurator(e);
        }

        return new ManagedTask(task, configurator, this.createContext(taskHost))
    }

    public createManagedTask(taskHostId: string): Promise<ManagedTask>;
    public createManagedTask(taskHost: TaskHost): Promise<ManagedTask>;
    public async createManagedTask(data: TaskHost | string) {
        let taskHost: TaskHost;
        if (typeof data === "string") {
            taskHost = await this.getTaskHost(data);
        }
        else {
            taskHost = data;
        }
        const configurator = await this.getConfigurator(taskHost);
        const context = this.createContext(taskHost);
        const inst = await configurator.create(context);
        return new ManagedTask(inst, configurator, context);
    }

    private async getTaskHost(id: string) {
        if (this.taskHosts.has(id)) {
            return this.taskHosts.get(id)!;
        }

        const res = await fetch(`./api/task-host/${id}`, { method: "get" });
        if (res.ok) {
            const taskHost = TaskHostModel.parse(await res.json())
            this.taskHosts.set(taskHost.id, taskHost);
            return taskHost;
        }
        else {
            return getNotFoundTaskHost(id);
        }
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
                const configurator: any = (await import(importUrl)).default;
                if (typeof configurator !== "object" || configurator === null || Object.values(configurator).some(fn => typeof fn !== "function")) {
                    throw new Error("Configurator format is wrong!");
                }

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
            idGenerator: () => Math.floor(Math.random() * 1000000000)
        };
    }
}
