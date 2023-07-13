import cloneDeep from "clone-deep";
import { makeAutoObservable, observable, reaction } from "mobx";
import { NodeEditorRenderer } from "../lib/node-editor";
import { Task, Deployment, taskToTemplateNode, taskToMockNode } from "../lib/task";
import { v4 as uuidv4 } from 'uuid';

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

    @observable
    private _status: string;

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

        this.reactionDisposers.push(reaction(() => this.status, () => {
            this.editor.readOnly = this.status === 'running';
        }));
        this.editor = new NodeEditorRenderer();
        this.tasks.forEach(task => this.addTaskToEditor(task));
    }

    public destroy() {
        this.reactionDisposers.forEach(disposer => disposer());
        this.editor.destroy();
    }

    public async startListening() {
    }
    public async stopListening() {
    }
    
    public async createTaskFromTemplate(template: Task) {
        const task = cloneDeep(template);
        task.id = uuidv4();
        task.stream_groups.forEach(group => {
            group.inputs.forEach(input => {
                input.ref_id = uuidv4();
                input.topic_id = uuidv4();
            });
            group.outputs.forEach(output => {
                output.topic_id = uuidv4();
            });
        });
        
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
    private async addTaskToEditor(task: Task) {
        const node = taskToMockNode(task);
        this.editor.addNode(node, true);
    }
}