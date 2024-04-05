import { z } from "zod";
import { ManagedTask } from "../lib/task";
import { FullTaskModel } from "../model/task";
import { TaskManager } from "./task-manager";
import { action, makeObservable, observable } from "mobx";
import { createStateContext } from "./util";
import { FullDeployment } from "../types/deployment";
import _ from "underscore";
import { FullDeploymentModel } from "../model/deployment";

export class DeploymentState {
    public readonly tasks: Map<string, ManagedTask> = observable.map();

    public get id() {
        return this.deployment.id;
    }
    
    public get running() {
        return this.deployment.running;
    }

    private taskManager: TaskManager;
    private deployment: FullDeployment;

    constructor(deployment: FullDeployment, taskManager: TaskManager) {
        this.deployment = deployment
        this.taskManager = taskManager;
        makeObservable(this, {
            loadTasks: action,
            addTask: action,
            deleteTask: action,
            ...({
                deployment: observable,
            } as any)
        });
    }

    public async start() {
        if (this.running) {
            throw new Error("Can not start a deployment that is running.");
        }
        this.deployment = FullDeploymentModel.parse(await fetch(`/api/deployment/${this.id}/start`, { method: "post" }).then(res => res.json()));
        if (this.deployment.running) {
            await this.loadTasks();
        }
    }
    public async stop() {
        if (!this.running) {
            throw new Error("Can not stop a deployment that is not running.");
        }
        this.deployment = FullDeploymentModel.parse(await fetch(`/api/deployment/${this.id}/stop`, { method: "post" }).then(res => res.json()));
        if (!this.deployment.running) {
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
        await this.putTask(task);
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

    private async putTask(task: ManagedTask) {
        if (this.running) throw new Error("Deployment is running!");
        const result = await fetch(`/api/task`, {
            method: "put",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                deployment_id: this.id,
                ...task.task
            })
        });

        if (!result.ok) {
            throw new Error("Failed to update task in backend!");
        }
    }

    private trackTask(task: ManagedTask) {
        task.on("updated", _.throttle(() => this.putTask(task), 1000)); // TODO: memory management
    }
}

export const [DeploymentContext, useDeployment] = createStateContext<DeploymentState>();