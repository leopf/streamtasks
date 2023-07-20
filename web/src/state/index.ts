import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, DeploymentBase, Task } from "../lib/task";
import { DeploymentState } from "./deployment";
import { Dashboard } from "../types";
import { createTransformer } from "mobx-utils";
import { SystemLogsState } from "./system-logs";

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

    public systemLogs = new SystemLogsState();

    @computed
    public get deployments() {
        return [...this._deployments];
    }

    @computed
    public get dashboards() {
        return [...this._dashboards];
    }

    constructor() {
        makeAutoObservable(this);
    }

    public getDashboard = createTransformer((id: string) => this._dashboards.find(d => d.id === id));

    public async init() {
        await Promise.all([
            this.loadTaskTemplates(),
            this.loadDeployments(),
            this.loadDashboards(),
            this.systemLogs.init()
        ])
        this._initialized = true;
    }

    public replaceDeployment(deployment: Deployment) {
        this._deployments = [
            ...this._deployments.filter(d => d.id !== deployment.id),
            deployment,
        ];
    }
    public async loadDeployment(id: string) {
        const res = await fetch(`/api/deployment/${id}`);
        if (!res.ok) return undefined;
        const deployment: Deployment = await res.json();
        const deploymentState = new DeploymentState(this, deployment);
        await deploymentState.init();
        return deploymentState;
    }
    public async createDeployment(label: string) {
        const res = await fetch('/api/deployment', {
            method: 'POST',
        });
        const json = await res.json();
        const deployment: Deployment = json;
        this._deployments.push(deployment);
        return deployment;
    }

    public async loadDeployments() {
        const res = await fetch('/api/deployments');
        const json = await res.json();
        this._deployments = json;
    }

    public async loadDashboards() {
        const res = await fetch('/api/dashboards');
        const json = await res.json();
        this._dashboards = json;
    }

    private async loadTaskTemplates() {
        const res = await fetch('/api/task-templates');
        const json = await res.json();
        this.taskTemplates = json;
        return json;
    }
}

export const state = new RootState();