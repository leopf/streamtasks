import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, Task } from "../lib/task";
import { DeploymentState } from "./deployment";
import { LogEntry } from "../model";

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

    @observable
    public logs: LogEntry[] = [];

    constructor() {
        if (process.env.NODE_ENV === 'development') {
            for (let i = 0; i < 100; i++) {
                this.logs.push({
                    level: 'info',
                    message: 'Hello world',
                    timestamp: new Date()
                });
            }
        }
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
    public async createDeployment(label: string) {
        const res = await fetch('/api/deployment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ label })
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