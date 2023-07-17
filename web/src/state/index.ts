import { computed, makeAutoObservable, observable } from "mobx";
import { Deployment, DeploymentBase, Task } from "../lib/task";
import { DeploymentState } from "./deployment";
import { LogEntry, LogEntryModel } from "../model";
import { Dashboard } from "../types";
import { createTransformer } from "mobx-utils";

export class SystemLogsState {
    @observable
    private _logs: LogEntry[] = [];

    @observable
    private _open = false;

    @computed
    public get logs() {
        return [...this._logs].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    }

    @computed
    public get open() {
        return this._open;
    }

    constructor() {
        makeAutoObservable(this);
    }

    public async init() {
        await this.loadLogs(100);
    }

    public toggleOpen() {
        this._open = !this._open;
    }

    public async completeLoadLogs() {
        const batchSize = 10;
        const maxTimeDiff = 1000 * 60 * 60 * 24; // 7 days
        let currentTime = Date.now();
        const timeDifference = Math.min(currentTime - (this._logs.at(-1)?.timestamp?.getTime() ?? 0), maxTimeDiff);
        const targetTime = currentTime - timeDifference;

        let batchIndex = 0;
        while (currentTime > targetTime) {
            const logs = await this.fetchLogs(batchSize, batchIndex * batchSize);
            if (logs.length === 0) break;
            this.addLogs(logs);
            currentTime = Math.min(...logs.map(l => l.timestamp.getTime()));
            batchIndex++;
        }
    }

    private async loadLogs(count: number, offset: number = 0) {
        const logs = await this.fetchLogs(count, offset);
        this.addLogs(logs);
    }
    private async fetchLogs(count: number, offset: number = 0) {
        const res = await fetch(`/api/logs?count=${count}&offset=${offset}`);
        const json: LogEntry[] = await res.json();
        const logs: LogEntry[] = json.map((l: any) => LogEntryModel.parse(l));
        return logs;
    }
    private addLogs(logs: LogEntry[], loadedIds?: Set<string>) {
        const _loadedIds = loadedIds ?? new Set(logs.map(l => l.id));
        this._logs = [
            ...this._logs.filter(l => !_loadedIds.has(l.id)),
            ...logs
        ]
    }
}

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

    public async loadDeployment(id: string) {
        const res = await fetch(`/api/deployment/${id}`);
        if (!res.ok) return undefined;
        const deployment: Deployment = await res.json();
        return new DeploymentState(deployment);
    }
    public async createDeployment(label: string) {
        const res = await fetch('/api/deployment', {
            method: 'POST',
            // headers: {
            //     'Content-Type': 'application/json'
            // },
            // body: JSON.stringify({ label })
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