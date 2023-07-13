import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, Task } from "../lib/task";
import { DeploymentState } from "./deployment";

export class RootState {
    @observable
    public taskTemplates: Task[] = [];

    public get initialized() {
        return this._initialized;
    }
    public get deployments() {
        return this._deployments.slice();
    }
    @computed
    public get selectedDeployment() {
        return this._deployments.find(d => d.id === this.selectedDeploymentId);
    }

    @observable
    private _deployments: DeploymentState[] = [];

    @observable
    private selectedDeploymentId?: string;

    @observable
    private _initialized = false;

    constructor() {
        makeAutoObservable(this);
    }

    public async init() {
        await Promise.all([
            this.loadTaskTemplates(),
            this.loadDeployments()
        ])
        this._initialized = true;
    }

    public async createDeployment() {
        const res = await fetch('/api/deployment', {
            method: 'POST',
        });
        const json = await res.json();
        const deployment: Deployment = json;
        this._deployments.push(new DeploymentState(deployment));
        this.selectedDeploymentId = deployment.id;
    }

    public async loadDeployments() {
        const res = await fetch('/api/deployments');
        const deployments: Deployment[] = await res.json();
        const loadedDeployments = new Set(this._deployments.map(d => d.id));
        this._deployments.push(...deployments.filter(d => !loadedDeployments.has(d.id)).map(d => new DeploymentState(d)));
    }

    private async loadTaskTemplates() {
        const res = await fetch('/api/task-templates');
        const json = await res.json();
        this.taskTemplates = json;
        return json;
    }
}

export const state = new RootState();