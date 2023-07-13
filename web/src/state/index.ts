import { makeAutoObservable, observable } from "mobx";
import { Task } from "../lib/task";

export class RootState {
    @observable
    public taskTemplates: Task[] = [];

    @observable
    private _initialized = false;
    public get initialized() {
        return this._initialized;
    }

    constructor() {
        makeAutoObservable(this);
    }

    public async init() {
        await this.loadTaskTemplates();
        this._initialized = true;
    }

    private async loadTaskTemplates() {
        const res = await fetch('/api/task-templates');
        const json = await res.json();
        this.taskTemplates = json;
        return json;
    }
}

export const state = new RootState();