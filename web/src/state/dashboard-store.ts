import { z } from "zod";
import { DashboardModel } from "../model/dashboard";
import { Dashboard } from "../types/dashboard";
import { computed, makeObservable, observable } from "mobx";
import _ from "underscore";

export class DashboardStore {
    private _dashboards: Map<string, Dashboard> = observable.map();
    public putThrottled = _.throttle(async (dashboard: Dashboard) => await this.put(dashboard), 1000);

    public get dashboards() {
        return Array.from(this._dashboards.values())
    }

    constructor() {
        makeObservable({
            dashboards: computed
        })
    }

    public async loadInDeployment(deploymentId: string) {
        const result = await fetch(`./api/deployment/${deploymentId}/dashboards`).then(res => res.json());
        const tasks = z.array(DashboardModel).parse(result);
        this.putDashboards(...tasks);
        return tasks;
    }

    public async loadOne(id: string) {
        this.putDashboards(DashboardModel.parse(await fetch(`./api/dashboard/${id}`).then(res => res.json())))
    }

    public async get(id: string) {
        const found = this.dashboards.find(d => d.id === id);
        if (found) {
            return found;
        }
        try {
            return await this.loadOne(id);
        } catch {
            return undefined;
        }
    }

    public async put(dashboard: Dashboard) {
        const result = await fetch(`./api/dashboard`, {
            method: "put",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(dashboard)
        });

        if (!result.ok) {
            throw new Error("Failed to update task in backend!");
        }

        const newDashboard = DashboardModel.parse(await result.json());
        this.putDashboards(newDashboard);
        return newDashboard;
    }

    public async delete(id: string) {
        const result = await fetch(`./api/dashboard/${id}`, { method: "delete" });
        if (!result.ok) {
            throw new Error("Failed to delete!")
        }
        this._dashboards.delete(id);
    }

    private putDashboards(...dashboards: Dashboard[]) {
        for (const task of dashboards) {
            try {
                this._dashboards.set(task.id, DashboardModel.parse(task))
            }
            catch {}
        }
    }
}