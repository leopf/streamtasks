import cloneDeep from "clone-deep";
import { computed, makeAutoObservable, observable, reaction } from "mobx";
import { createTransformer } from "mobx-utils";
import { NodeEditorRenderer } from "../lib/node-editor";
import { Task, Deployment, cloneTask } from "../lib/task";
import { v4 as uuidv4 } from 'uuid';
import { TaskNode } from "../lib/task/node";

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

    @computed
    public get readOnly() {
        return this.status === 'running';
    }

    @observable
    private _status: string;

    @observable.shallow
    private taskNodeMap = new Map<string, TaskNode>();

    private get deployment(): Deployment {
        return {
            id: this.id,
            label: this.label,
            status: this._status as any,
            tasks: this.tasks,
        };
    }

    private reactionDisposers: (() => void)[] = [];

    constructor(deployment: Deployment) {
        makeAutoObservable(this);
        this.id = deployment.id;
        this.tasks = deployment.tasks;
        this.label = deployment.label;
        this._status = deployment.status;

        this.reactionDisposers.push(reaction(() => this.readOnly, () => {
            this.editor.readOnly = this.readOnly;
        }));
        this.editor = new NodeEditorRenderer();
        this.tasks.forEach(task => this.addTaskToEditor(task));
    }

    public getTaskNodeById = createTransformer((id: string) => this.taskNodeMap.get(id));

    public destroy() {
        this.reactionDisposers.forEach(disposer => disposer());
        this.editor.destroy();
    }

    public async startListening() {
    }
    public async stopListening() {
    }

    public async createTaskFromTemplate(template: Task) {
        const task = cloneTask(template);
        this.tasks.push(task);
        this.addTaskToEditor(task);
    }
    public async start() {
        const res = await fetch(`/api/deployment/${this.id}/start`, {
            method: 'POST',
        });
        const json = await res.json();
        this._status = json.status;
    }
    public async stop() {
        const res = await fetch(`/api/deployment/${this.id}/stop`, {
            method: 'POST',
        });
        const json = await res.json();
        this._status = json.status;
    }
    public async reload() {
        const res = await fetch(`/api/deployment/${this.id}`, {
            method: 'GET'
        });
        const deployment: Deployment = await res.json();
        this.tasks = deployment.tasks;
        this.label = deployment.label;
        this._status = deployment.status;

        this.editor.clear();
        this.tasks.forEach(task => this.addTaskToEditor(task));
    }
    public async save() {
        const res = await fetch(`/api/deployment/${this.id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(this.deployment),
        });
        const json = await res.json();
        this._status = json.status;
    }
    public removeTask(task: Task) {
        this.editor.deleteNode(task.id);
        this.tasks = this.tasks.filter(t => t.id !== task.id);
        this.taskNodeMap.delete(task.id);
    }
    private async addTaskToEditor(task: Task) {
        const node = new TaskNode(task);
        this.taskNodeMap.set(task.id, node);
        await this.editor.addNode(node, true);
    }
}