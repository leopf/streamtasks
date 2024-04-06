import { z } from "zod";
import { ManagedTask } from "../lib/task";
import { FullTaskModel, StoredTaskModel } from "../model/task";
import { TaskManager } from "./task-manager";
import { action, computed, makeObservable, observable, observe, reaction } from "mobx";
import { createStateContext } from "./util";
import _ from "underscore";
import { FullDeploymentModel } from "../model/deployment";
import { RootStore } from "./root-store";
import { StoredTask } from "../types/task";
import deepEqual from "deep-equal";

export class DeploymentState {
    public readonly tasks: Map<string, ManagedTask> = observable.map();

    public get id() {
        return this.deployment.id;
    }

    public get running() {
        return this.deployment.running;
    }

    public get label() {
        return this.deployment.label;
    }

    public get deployment() {
        return this.rootStore.getDeployment(this.deploymentId) ?? (() => { throw new Error("Deployment not found!") })();
    }

    private readonly _taskStateCache = new Map<string, StoredTask>();
    private taskManager: TaskManager;
    private deploymentId: string;
    private rootStore: RootStore;

    constructor(deploymentId: string, rootStore: RootStore, taskManager: TaskManager) {
        this.deploymentId = deploymentId
        this.rootStore = rootStore
        this.taskManager = taskManager;
        makeObservable(this, {
            loadTasks: action,
            addTask: action,
            deleteTask: action,
            deployment: computed
        });
        observe(this.tasks, (change) => { // TODO: memory management
            if (change.type == "add" || change.type == "update") {
                this._taskStateCache.set(change.newValue.id, StoredTaskModel.parse(change.newValue.task))
            }
            else if (change.type === "delete") {
                this._taskStateCache.delete(change.oldValue.id);
            }
        });
    }

    public async start() {
        if (this.running) {
            throw new Error("Can not start a deployment that is running.");
        }
        const deployment = FullDeploymentModel.parse(await fetch(`/api/deployment/${this.id}/start`, { method: "post" }).then(res => res.json()));
        this.rootStore.insertDeployment(deployment);
        if (deployment.running) {
            await this.loadTasks();
        }
    }
    public async stop() {
        if (!this.running) {
            throw new Error("Can not stop a deployment that is not running.");
        }
        const deployment = FullDeploymentModel.parse(await fetch(`/api/deployment/${this.id}/stop`, { method: "post" }).then(res => res.json()));
        this.rootStore.insertDeployment(deployment);
        if (!deployment.running) {
            await this.loadTasks();
        }
    }

    public async loadTasks() {
        const result = await fetch(`/api/deployment/${this.id}/tasks`).then(res => res.json());
        const storedTasks = z.array(FullTaskModel).parse(result)
        const newTasks = new Map(storedTasks.map(t => [t.id, t]));
        for (const taskId of this.tasks.keys()) {
            if (!newTasks.has(taskId)) {
                this.tasks.delete(taskId);
            }
        }
        for (const task of this.tasks.values()) {
            task.updateData(newTasks.get(task.id)!);
            newTasks.delete(task.id);
        }
        for (const task of newTasks.values()) {
            const mTask = await this.taskManager.toManagedTask(task);
            this.trackTask(mTask);
            this.tasks.set(mTask.id, mTask);
        }
    }

    public async addTask(task: ManagedTask) {
        if (this.running) throw new Error("Deployment is running!");
        await this.putTask(StoredTaskModel.parse(task.task));
        this.tasks.set(task.id, task);
        this.trackTask(task);
    }

    public async deleteTask(task: ManagedTask) {
        if (this.running) throw new Error("Deployment is running!");
        const result = await fetch(`/api/task/${task.id}`, { method: "delete" });
        if (!result.ok) {
            throw new Error("Failed to delete!")
        }
        this.tasks.delete(task.id);
    }

    private async putTask(task: StoredTask) {
        if (this.running) throw new Error("Deployment is running!");
        const result = await fetch(`/api/task`, {
            method: "put",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                deployment_id: this.id,
                ...task
            })
        });

        if (!result.ok) {
            throw new Error("Failed to update task in backend!");
        }
    }

    // TODO: memory management
    private trackTask(task: ManagedTask) {
        task.on("updated", _.throttle(async () => {
            try {
                const oldValue = this._taskStateCache.get(task.id);
                const newValue = StoredTaskModel.parse(task.task);
                if (!oldValue || !deepEqual(oldValue, newValue)) {
                    await this.putTask(newValue);
                }
            } catch {}
        }, 1000));
    }
}

export const [DeploymentContext, useDeployment] = createStateContext<DeploymentState>();