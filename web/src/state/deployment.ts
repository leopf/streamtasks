import { z } from "zod";
import { ManagedTaskInstance } from "../lib/task";
import { StoredTaskInstanceModel } from "../model/task";
import { TaskManager } from "./task-manager";
import { action, makeObservable, observable } from "mobx";

export class DeploymentState {
    public readonly id: string;
    public readonly tasks: Map<string, ManagedTaskInstance> = observable.map();

    private taskManager: TaskManager;

    constructor(id: string, taskManager: TaskManager) {
        this.id = id;
        this.taskManager = taskManager;
        makeObservable(this, {
            loadTasks: action,
            addTask: action,
            deleteTask: action 
        });
    }

    public async loadTasks() {
        const result = await fetch(`/api/deployment/${this.id}/tasks`, { method: "get" }).then(res => res.json());
        const storedTasks = z.array(StoredTaskInstanceModel).parse(result)
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
            const mTask = await this.taskManager.toManagedTaskInstance(task);
            this.trackTask(mTask);
            this.tasks.set(mTask.id, mTask);
        }
    }

    public async addTask(task: ManagedTaskInstance) {
        // await this.putTask(task);
        this.tasks.set(task.id, task);
        this.trackTask(task);
    }

    public async deleteTask(task: ManagedTaskInstance) {
        const result = await fetch(`/api/deployment/${this.id}/task/${task.id}`, { method: "delete" });
        if (!result.ok) {
            throw new Error("Failed to delete!")
        }
        this.tasks.delete(task.id);
    }

    private async putTask(task: ManagedTaskInstance) {
        const result = await fetch(`/api/deployment/${this.id}/task`, { 
            method: "put",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(task.storedInstance)
        });

        if (!result.ok) {
            throw new Error("Failed to update task in backend!");
        }
    }
    
    private trackTask(task: ManagedTaskInstance) {

    }
}