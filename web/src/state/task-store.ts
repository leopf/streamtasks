import { z } from "zod";
import { FullTaskModel, StoredTaskModel } from "../model/task";
import { StoredTask } from "../types/task";
import deepEqual from "deep-equal";

export class TaskStore {
    private _storedTasks = new Map<string, StoredTask>();

    public async loadTasksInDeployment(deploymentId: string) {
        const result = await fetch(`/api/deployment/${deploymentId}/tasks`).then(res => res.json());
        const tasks = z.array(FullTaskModel).parse(result);
        this.putStoredTasks(...tasks);
        return tasks;
    }

    public async putTask(task: StoredTask, deploymentId: string, force: boolean = false) {
        const storedTask = StoredTaskModel.parse(task);
        if (!force && deepEqual(storedTask, this._storedTasks.get(task.id))) return;
        const result = await fetch(`/api/task`, {
            method: "put",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                deployment_id: deploymentId,
                ...storedTask
            })
        });

        if (!result.ok) {
            throw new Error("Failed to update task in backend!");
        }

        const newTask = FullTaskModel.parse(await result.json());
        this.putStoredTasks(newTask);
        return newTask;
    }

    public async deleteTask(taskId: string) {
        const result = await fetch(`/api/task/${taskId}`, { method: "delete" });
        if (!result.ok) {
            throw new Error("Failed to delete!")
        }
        this._storedTasks.delete(taskId);
    }

    private putStoredTasks(...tasks: StoredTask[]) {
        for (const task of tasks) {
            try {
                this._storedTasks.set(task.id, StoredTaskModel.parse(task))
            }
            catch {}
        }
    }
}