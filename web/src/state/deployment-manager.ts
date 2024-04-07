import { ManagedTask } from "../lib/task";
import { action, computed, makeObservable, observable, reaction } from "mobx";
import { createStateContext } from "./util";
import _ from "underscore";
import { RootStore } from "./root-store";
import { UpdateTaskInstanceMessageModel } from "../model/task-messages";
import EventEmitter from "eventemitter3";

class DeploymentTaskInstanceUpdater {
    private deploymentManager: DeploymentManager;
    private ws: WebSocket;
    public open: boolean = false;
    public errorCount: number = 0;

    constructor(deploymentManager: DeploymentManager) {
        this.deploymentManager = deploymentManager;
        this.ws = new WebSocket(`ws://${location.host}/deployment/${deploymentManager.id}/task-instances`);
        this.ws.addEventListener("open", () => this.open = true);
        this.ws.addEventListener("message", e => this.onData(e.data));
        this.ws.addEventListener("error", () => this.errorCount++);
        this.ws.addEventListener("close", () => this.open = false);
    }

    public destroy() {
        this.ws.close();
    }

    private onData(data: any) {
        try {
            const message = UpdateTaskInstanceMessageModel.parse(JSON.parse(data));
            const task = this.deploymentManager.tasks.get(message.id);
            task?.updateData({ task_instance: message.task_instance });
        } catch { }
    }
}

export class DeploymentManager extends EventEmitter<{ "taskUpdated": [ManagedTask] }> {
    public readonly tasks: Map<string, ManagedTask> = observable.map();

    public get id() {
        return this.deployment.id;
    }

    public get running() {
        return this.deployment.status !== "offline";
    }

    public get label() {
        return this.deployment.label;
    }

    public get deployment() {
        return this.rootStore.deployment.get(this.deploymentId) ?? (() => { throw new Error("Deployment not found!") })();
    }

    private deploymentId: string;
    private rootStore: RootStore;

    private taskInstanceUpdater?: DeploymentTaskInstanceUpdater;
    private disposers: (() => void)[] = [];

    constructor(deploymentId: string, rootStore: RootStore) {
        super();
        this.deploymentId = deploymentId
        this.rootStore = rootStore
        makeObservable(this, {
            loadTasks: action,
            addTask: action,
            deleteTask: action,
            deployment: computed
        });
        this.disposers.push(reaction(() => this.running, () => {
            this.taskInstanceUpdater?.destroy();
            this.taskInstanceUpdater = undefined;
            if (this.running) {
                this.taskInstanceUpdater = new DeploymentTaskInstanceUpdater(this);
            }
        }, { fireImmediately: true }));
    }

    public async start() {
        if (this.running) {
            throw new Error("Can not start a deployment that is running.");
        }
        await this.rootStore.deployment.schedule(this.id);
        if (this.running) {
            await this.loadTasks();
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
        task.removeAllListeners("updated");
        this.tasks.delete(task.id);
    }

    public destroy() {
        this.removeAllListeners();
        this.disposers.forEach(d => d());
        this.disposers = [];
        this.taskInstanceUpdater?.destroy();
    }

    private trackTask(task: ManagedTask) {
        const saveFn = _.throttle(async () => await this.rootStore.task.putTask(task.task, this.id), 1000);
        const updatedFn = () => {
            this.emit("taskUpdated", task);
            saveFn();
        };
        task.on("updated", saveFn, 1000);
        this.disposers.push(() => task.off("updated", updatedFn));
    }
}

export const [DeploymentContext, useDeployment] = createStateContext<DeploymentManager>();