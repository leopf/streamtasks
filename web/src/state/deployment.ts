import { action, computed, makeAutoObservable, observable, reaction } from "mobx";
import { createTransformer } from "mobx-utils";
import { NodeEditorRenderer } from "../lib/node-editor";
import { Task, Deployment, cloneTask, DeploymentBase, DeploymentStatus, deploymentStatusIsStarted } from "../lib/task";
import { TaskNode } from "../lib/task/node";
import { RootState } from ".";

export class DeploymentState {
    public readonly editor: NodeEditorRenderer;
    public readonly id: string;

    public get status() {
        return this._status;
    }

    public get label() {
        return this._label;
    }
    public set label(value: string) {
        this.validateAllowEdit();
        this._label = value;
    }

    @computed
    public get isStarted() {
        return deploymentStatusIsStarted(this._status);
    }

    @computed
    public get readOnly() {
        return this.isStarted && !this.disabled;
    }

    @observable
    private _status: DeploymentStatus;

    @observable.shallow
    private taskNodeMap = new Map<string, TaskNode>();

    @observable
    private _tasks: Task[] = [];

    @observable
    private _label: string;

    @computed
    private get deploymentBase(): DeploymentBase {
        return {
            id: this.id,
            label: this._label,
        };
    }
    @computed
    private get deployment(): Deployment {
        return {
            ...this.deploymentBase,
            status: this._status,
            tasks: this._tasks,
        };
    }
    
    private readonly disabled: boolean = false;
    private rootState: RootState;
    private reactionDisposers: (() => void)[] = [];
    
    private statusRefreshHandle?: number;

    constructor(rootState: RootState, deployment: Deployment, disabled: boolean = false) {
        makeAutoObservable(this);
        this.rootState = rootState;
        this.id = deployment.id;
        this._tasks = deployment.tasks;
        this._label = deployment.label;
        this._status = deployment.status;
        this.disabled = disabled;

        this.editor = new NodeEditorRenderer();
    }

    public getTaskNodeById = createTransformer((id: string) => this.taskNodeMap.get(id));
    public getTaskById = createTransformer((id: string) => this._tasks.find(t => t.id === id));

    @action
    public async init() {
        for (const task of this._tasks) {
            await this.addTaskToEditor(task, false);
        }
        this.reactionDisposers.push(reaction(() => this.readOnly, () => this.editor.readOnly = this.readOnly, { fireImmediately: true }));

        if (!this.disabled) {
            this.reactionDisposers.push(reaction(() => this.deploymentBase, () => this.rootState.replaceDeployment(this.deployment)));
            this.reactionDisposers.push(reaction(() => JSON.stringify(this.deployment), () => this.save(), {
                delay: 1000,
            })); // TODO: there must be a better way to do this
        }
    }

    @action
    public destroy() {
        this.reactionDisposers.forEach(disposer => disposer());
        this.editor.destroy();
    }

    public startListening() {
        if (this.statusRefreshHandle) this.stopListening();
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
        this.validateAllowEdit();
        const task = cloneTask(template);
        this._tasks.push(task);
        const reactiveTask = this.getTaskById(task.id);
        await this.addTaskToEditor(reactiveTask!); // this is safe because we just pushed it
    }
    @action
    public async updateStatus() {
        const res = await fetch(`/api/deployment/${this.id}/status`);
        const data: { status: DeploymentStatus } = await res.json();
        this.applyStatus(data.status);
    }
    @action
    public async start() {
        if (this.isStarted) {
            console.warn('Deployment is already started');
            return;
        }
        const res = await fetch(`/api/deployment/${this.id}/start`, {
            method: 'POST',
        });
        const data: { status: DeploymentStatus } = await res.json();
        this.applyStatus(data.status);
    }
    @action
    public async stop() {
        if (!this.isStarted) {
            console.warn('Attempted to stop a deployment that is not started');
            return;
        }
        const res = await fetch(`/api/deployment/${this.id}/stop`, {
            method: 'POST',
        });
        const data: { status: DeploymentStatus } = await res.json();
        this.applyStatus(data.status);
    }
    @action
    public async reload() {
        const res = await fetch(`/api/deployment/${this.id}`, {
            method: 'GET'
        });
        const deployment: Deployment = await res.json();
        this._tasks = deployment.tasks;
        this._label = deployment.label;
        this._status = deployment.status;

        this.editor.clear();
        for (const task of this._tasks) {
            await this.addTaskToEditor(task, false);
        }
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
        this.validateAllowEdit();
        this.editor.deleteNode(task.id);
        this._tasks = this._tasks.filter(t => t.id !== task.id);
        this.taskNodeMap.delete(task.id);
    }
    private async addTaskToEditor(task: Task, center: boolean = true) {
        const node = new TaskNode(task);
        this.taskNodeMap.set(task.id, node);
        await this.editor.addNode(node, center);
    }
    private applyStatus(status: DeploymentStatus) {
        this._status = status;
    }

    private validateAllowEdit() {
        if (this.readOnly) {
            throw new Error('Attempted to edit a read-only deployment');
        }
    }
}