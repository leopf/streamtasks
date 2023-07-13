import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, Task } from "../lib/task";
import { DeploymentState } from "./deployment";

export class RootState {
    @observable
    public taskTemplates: Task[] = [];

    public get initialized() {
        return this._initialized;
    }

    @observable
    private deployments: Deployment[] = [];

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

    public getDeployment(id: string) {
        const deployment = this.deployments.find(d => d.id === id);
        if (!deployment) return undefined;
        return new DeploymentState(deployment);
    }
    public async createDeployment() {
        const res = await fetch('/api/deployment', {
            method: 'POST',
        });
        const json = await res.json();
        const deployment: Deployment = json;
        this.deployments.push(deployment);
        return deployment;
    }

    public async loadDeployments() {
        const res = await fetch('/api/deployments');
        this.deployments = await res.json();;
    }

    private async loadTaskTemplates() {
        const res = await fetch('/api/task-templates');
        const json = await res.json();
        this.taskTemplates = json;
        return json;
    }
}

export const state = new RootState();