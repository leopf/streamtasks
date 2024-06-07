import { z } from "zod";
import { DashboardModel } from "../model/dashboard";
import { computed, makeObservable, observable } from "mobx";
import _ from "underscore";
import { Dashboard } from "../types/dashboard";

export class DashboardStore {
    public dashboards: Map<string, Dashboard> = observable.map();

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
        const found = this.dashboards.get(id);
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
        this.dashboards.delete(id);
    }

    private putDashboards(...dashboards: Dashboard[]) {
        for (const task of dashboards) {
            try {
                this.dashboards.set(task.id, DashboardModel.parse(task))
            }
            catch {}
        }
    }
}