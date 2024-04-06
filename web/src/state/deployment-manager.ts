import { ManagedTask } from "../lib/task";
import { action, computed, makeObservable, observable } from "mobx";
import { createStateContext } from "./util";
import _ from "underscore";
import { RootStore } from "./root-store";

export class DeploymentManager {
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
        return this.rootStore.deployment.get(this.deploymentId) ?? (() => { throw new Error("Deployment not found!") })();
    }

    private deploymentId: string;
    private rootStore: RootStore;
    private disposers: (() => void)[] = [];

    constructor(deploymentId: string, rootStore: RootStore) {
        this.deploymentId = deploymentId
        this.rootStore = rootStore
        makeObservable(this, {
            loadTasks: action,
            addTask: action,
            deleteTask: action,
            deployment: computed
        });
    }

    public async start() {
        if (this.running) {
            throw new Error("Can not start a deployment that is running.");
        }
        await this.rootStore.deployment.start(this.id);
        if (this.running) {
            await this.loadTasks();
        }
    }
    public async stop() {
        if (!this.running) {
            throw new Error("Can not stop a deployment that is not running.");
        }
        await this.rootStore.deployment.stop(this.id);
        if (!this.running) {
            await this.loadTasks();
        }
    }

    public async loadTasks() {
        const tasks = await this.rootStore.task.loadTasksInDeployment(this.id);
        const newTasks = new Map(tasks.map(t => [t.id, t]));
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
            const mTask = await this.rootStore.taskManager.toManagedTask(task);
            this.trackTask(mTask);
            this.tasks.set(mTask.id, mTask);
        }
    }

    public async addTask(task: ManagedTask) {
        if (this.running) throw new Error("Deployment is running!");
        await this.rootStore.task.putTask(task.task, this.id, true);
        this.tasks.set(task.id, task);
        this.trackTask(task);
    }

    public async deleteTask(task: ManagedTask) {
        if (this.running) throw new Error("Deployment is running!");
        await this.rootStore.task.deleteTask(task.id);
        this.tasks.delete(task.id);
    }

    public destroy() {
        this.disposers.forEach(d => d());
        this.disposers = [];
    }

    private trackTask(task: ManagedTask) {
        const updateFn = _.throttle(async () => await this.rootStore.task.putTask(task.task, this.id), 1000);
        task.on("updated", updateFn, 1000);
        this.disposers.push(() => task.off("updated", updateFn));
    }
}

export const [DeploymentContext, useDeployment] = createStateContext<DeploymentManager>();