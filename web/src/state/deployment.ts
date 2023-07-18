import cloneDeep from "clone-deep";
import { action, computed, makeAutoObservable, observable, reaction } from "mobx";
import { createTransformer } from "mobx-utils";
import { NodeEditorRenderer } from "../lib/node-editor";
import { Task, Deployment, cloneTask, DeploymentBase } from "../lib/task";
import { v4 as uuidv4 } from 'uuid';
import { TaskNode } from "../lib/task/node";
import { RootState } from ".";

export class DeploymentState {
    public readonly editor: NodeEditorRenderer;
    public readonly id: string;

    @observable
    public tasks: Task[] = [];

    @observable
    public label: string;

    public get status() {
        return this._status;
    }

    public get started() {
        return this._started;
    }

    @computed
    public get readOnly() {
        return this.status === 'running';
    }

    @observable
    private _status: string;

    @observable
    private _started: boolean = false;

    @observable.shallow
    private taskNodeMap = new Map<string, TaskNode>();

    
    @computed
    private get deploymentBase(): DeploymentBase {
        return {
            id: this.id,
            label: this.label,
            status: this._status as any,
        };
    }
    @computed
    private get deployment(): Deployment {
        return {
            ...this.deploymentBase,
            tasks: this.tasks,
        };
    }
    
    private rootState: RootState;
    private reactionDisposers: (() => void)[] = [];
    
    private statusRefreshHandle?: number;

    constructor(rootState: RootState, deployment: Deployment) {
        makeAutoObservable(this);
        this.rootState = rootState;
        this.id = deployment.id;
        this.tasks = deployment.tasks;
        this.label = deployment.label;
        this._status = deployment.status;

        this.reactionDisposers.push(reaction(() => this.readOnly, () => this.editor.readOnly = this.readOnly));
        this.reactionDisposers.push(reaction(() => this.deploymentBase, () => this.rootState.replaceDeployment(this.deployment)));
        this.reactionDisposers.push(reaction(() => JSON.stringify(this.deployment), () => this.save(), {
            delay: 1000,
        })); // TODO: there must be a better way to do this

        this.editor = new NodeEditorRenderer();
        this.tasks.forEach(task => this.addTaskToEditor(task, false));
    }

    public getTaskNodeById = createTransformer((id: string) => this.taskNodeMap.get(id));
    public getTaskById = createTransformer((id: string) => this.tasks.find(t => t.id === id));

    public destroy() {
        this.reactionDisposers.forEach(disposer => disposer());
        this.editor.destroy();
    }

    public startListening() {
        this.statusRefreshHandle = window.setInterval(async () => {
            await this.updateStatus();
        }, 1000);
    }
    public stopListening() {
        if (this.statusRefreshHandle) {
            clearInterval(this.statusRefreshHandle);
        }
    }

    @action
    public async createTaskFromTemplate(template: Task) {
        const task = cloneTask(template);
        this.tasks.push(task);
        const reactiveTask = this.getTaskById(task.id);
        this.addTaskToEditor(reactiveTask!); // this is safe because we just pushed it
    }
    @action
    public async updateStatus() {
        const res = await fetch(`/api/deployment/${this.id}/status`);
        const json = await res.json();
        this.applyStatus(json);
    }
    @action
    public async start() {
        const res = await fetch(`/api/deployment/${this.id}/start`, {
            method: 'POST',
        });
        const json = await res.json();
        this.applyStatus(json);
    }
    @action
    public async stop() {
        const res = await fetch(`/api/deployment/${this.id}/stop`, {
            method: 'POST',
        });
        const json = await res.json();
        this.applyStatus(json);
    }
    @action
    public async reload() {
        const res = await fetch(`/api/deployment/${this.id}`, {
            method: 'GET'
        });
        const deployment: Deployment = await res.json();
        this.tasks = deployment.tasks;
        this.label = deployment.label;
        this._status = deployment.status;

        this.editor.clear();
        this.tasks.forEach(task => this.addTaskToEditor(task, false));
    }
    @action
    public async save() {
        await fetch(`/api/deployment`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(this.deployment),
        });
    }
    @action
    public removeTask(task: Task) {
        this.editor.deleteNode(task.id);
        this.tasks = this.tasks.filter(t => t.id !== task.id);
        this.taskNodeMap.delete(task.id);
    }
    private async addTaskToEditor(task: Task, center: boolean = true) {
        const node = new TaskNode(task);
        this.taskNodeMap.set(task.id, node);
        await this.editor.addNode(node, center);
    }
    private applyStatus(statusInfo: { status: string, started: boolean }) {
        this._status = statusInfo.status;
        this._started = statusInfo.started;
    }
}