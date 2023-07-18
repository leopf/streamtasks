import { observable, computed, makeAutoObservable } from "mobx";
import { LogEntry, LogEntryModel } from "../model";

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