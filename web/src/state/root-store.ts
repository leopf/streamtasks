import { action, makeObservable, observable } from "mobx";
import { Deployment, FullDeployment, PartialDeployment } from "../types/deployment";
import { z } from "zod";
import { FullDeploymentModel } from "../model/deployment";
import { createStateContext } from "./util";

export class RootStore {
    private _deployments: Map<string, FullDeployment> = observable.map();
    public get deployments() {
        return Array.from(this._deployments.values());
    }

    constructor() {
        makeObservable(this, {
            loadDeployments: action,
            createDeployment: action,
            deleteDeployment: action,
            loadDeployment: action,
            updateDeployment: action
        });
    }

    public getDeployment(id: string) {
        return this._deployments.get(id);
    }
    public async loadDeployments() {
        const deployments = z.array(FullDeploymentModel).parse(await fetch("/api/deployments").then(res => res.json()));
        for (const deployment of deployments) {
            this._deployments.set(deployment.id, deployment);
        }
    }
    public async loadDeployment(id: string) {
        if (this._deployments.has(id)) {
            return this._deployments.get(id);
        }
        const res = await fetch(`/api/deployment/${id}`);
        if (!res.ok) {
            return undefined;
        }

        const deployment = FullDeploymentModel.parse(await res.json());
        if (deployment) {
            this._deployments.set(deployment.id, deployment);
        }
        return deployment;
    }
    public async deleteDeployment(id: string) {
        const res = await fetch(`/api/deployment/${id}`, { method: "delete" });
        if (res.ok) {
            this._deployments.delete(id);
        }
    }
    public async updateDeployment(deployment: Deployment) {
        const res = await fetch("/api/deployment", {
            method: "put",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(deployment)
        });
        if (res.ok) {
            const newDeployment = FullDeploymentModel.parse(await res.json());
            this._deployments.set(newDeployment.id, newDeployment);
        }
    }
    public async createDeployment(deployment: PartialDeployment) {
        const res = await fetch("/api/deployment", {
            method: "post",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(deployment)
        });
        if (res.ok) {
            const newDeployment = FullDeploymentModel.parse(await res.json());
            this._deployments.set(newDeployment.id, newDeployment);
        }
    }
    public insertDeployment(deployment: FullDeployment) {
        this._deployments.set(deployment.id, deployment);
    }
}

export const [ RootStoreContext, useRootStore ] = createStateContext<RootStore>();