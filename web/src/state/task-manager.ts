import { action, makeObservable, observable } from "mobx";
import { TaskConfigurator, TaskConfiguratorContext, TaskHost } from "../types/task";
import { z } from "zod";
import { TaskHostModel } from "../model/task";
import { ManagedTaskInstance } from "../lib/task";

export class TaskManager {
    public taskHosts: TaskHost[] = [];
    private configurators: Map<string, TaskConfigurator> = new Map();
    private idCounter: number = 1;

    constructor() {
        makeObservable(this, {
            taskHosts: observable,
            loadTaskHosts: action
        })
    }

    public async loadTaskHosts() {
        const result = await fetch("/api/task-hosts").then(res => res.json())
        this.taskHosts = z.array(TaskHostModel).parse(result)
        return this.taskHosts;
    }

    public createManagedTaskInstance(taskHostId: string): Promise<ManagedTaskInstance>;
    public createManagedTaskInstance(taskHost: TaskHost): Promise<ManagedTaskInstance>;
    public async createManagedTaskInstance(data: TaskHost | string) {
        let taskHost: TaskHost;
        if (typeof data === "string") {
            taskHost = this.taskHosts.find(th => th.id === data) ?? (() => { throw new Error("Task host not found!") })();
        }
        else {
            taskHost = data;
        }
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
            idGenerator: () => this.idCounter++
        };
    }
}