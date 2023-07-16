import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, DeploymentBase, Task } from "../lib/task";
import { DeploymentState } from "./deployment";
import { LogEntry } from "../model";
import { Dashboard } from "../types";
import { createTransformer } from "mobx-utils";

export class RootState {
    @observable
    public taskTemplates: Task[] = [];

    public get initialized() {
        return this._initialized;
    }

    @observable
    private _deployments: DeploymentBase[] = [];

    @observable
    private _dashboards: Dashboard[] = [];

    @observable
    private _initialized = false;

    @observable
    public logs: LogEntry[] = [];

    @observable
    public systemLogOpen = false;

    @computed
    public get deployments() {
        return [...this._deployments];
    }

    @computed
    public get dashboards() {
        return [...this._dashboards];
    }

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

    public getDashboard = createTransformer((id: string) => this._dashboards.find(d => d.id === id));

    public async init() {
        await Promise.all([
            this.loadTaskTemplates(),
            this.loadDeployments(),
            this.loadDashboards()
        ])
        this._initialized = true;
    }

    public async loadDeployment(id: string) {
        const res = await fetch(`/api/deployment/${id}`);
        if (!res.ok) return undefined;
        const deployment: Deployment = await res.json();
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
        this._deployments.push(deployment);
        return deployment;
    }

    public async loadDeployments() {
        const res = await fetch('/api/deployments');
        const json = await res.json();
        console.log("deployments: ", json);
        this._deployments = json;
    }

    public async loadDashboards() {
        const res = await fetch('/api/dashboards');
        const json = await res.json();
        console.log("dashboards: ", json);
        this._dashboards = json;
    }

    private async loadTaskTemplates() {
        const res = await fetch('/api/task-templates');
        const json = await res.json();
        console.log("task templates: ", json);
        this.taskTemplates = json;
        return json;
    }
}

export const state = new RootState();