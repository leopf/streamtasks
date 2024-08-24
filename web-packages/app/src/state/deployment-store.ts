import { action, computed, makeObservable, observable } from "mobx";
import { z } from "zod";
import { createTransformer } from "mobx-utils";
import { RootStore } from "./root-store";
import { DeploymentManager } from "./deployment-manager";
import { FullDeploymentModel } from "../model/deployment";
import { FullDeployment, Deployment, PartialDeployment } from "../types/deployment";

export class DeploymentStore {
    private _deployments: Map<string, FullDeployment> = observable.map();
    public get deployments() {
        return Array.from(this._deployments.values());
    }

    public get = createTransformer((id: string) => this._deployments.get(id))

    private rootStore: RootStore;
    private deploymentManagers = new Map<string, DeploymentManager>();

    constructor(rootStore: RootStore) {
        this.rootStore = rootStore;
        makeObservable(this, {
            deployments: computed,
            create: action,
            delete: action,
            loadAll: action,
            loadOne: action,
            start: action,
            stop: action,
            update: action,
            ...{
                "_deployments": observable
            }
        });
    }

    public async schedule(id: string) {
        const deployment = FullDeploymentModel.parse(await fetch(`./api/deployment/${id}/schedule`, { method: "post" }).then(res => res.json()));
        this._deployments.set(deployment.id, deployment);
    }
    public async start(id: string) {
        const deployment = FullDeploymentModel.parse(await fetch(`./api/deployment/${id}/start`, { method: "post" }).then(res => res.json()));
        this._deployments.set(deployment.id, deployment);
    }
    public async stop(id: string) {
        const deployment = FullDeploymentModel.parse(await fetch(`./api/deployment/${id}/stop`, { method: "post" }).then(res => res.json()));
        this._deployments.set(deployment.id, deployment);
    }

    public createManager(deployment: Deployment): DeploymentManager;
    public createManager(id: string): Promise<DeploymentManager | undefined>;
    public createManager(data: string | Deployment): Promise<DeploymentManager | undefined> | DeploymentManager {
        if (typeof data === "string") {
            return this.loadOne(data).then(d => d && this.createManager(d))
        }
        else {
            const manager = new DeploymentManager(data.id, this.rootStore);
            this.deploymentManagers.set(data.id, manager);
            return manager;
        }
    }
    public async loadAll() {
        const deployments = z.array(FullDeploymentModel).parse(await fetch("./api/deployments").then(res => res.json()));
        for (const deployment of deployments) {
            this._deployments.set(deployment.id, deployment);
        }
    }
    public async loadOne(id: string) {
        if (this._deployments.has(id)) {
            return this._deployments.get(id);
        }
        const res = await fetch(`./api/deployment/${id}`);
        if (!res.ok) {
            return undefined;
        }

        const deployment = FullDeploymentModel.parse(await res.json());
        if (deployment) {
            this._deployments.set(deployment.id, deployment);
        }
        return deployment;
    }
    public async delete(id: string) {
        const res = await fetch(`./api/deployment/${id}`, { method: "delete" });
        if (res.ok) {
            this._deployments.delete(id);
        }
    }
    public async update(deployment: Deployment) {
        const res = await fetch("./api/deployment", {
            method: "put",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(deployment)
        });
        if (res.ok) {
            const newDeployment = FullDeploymentModel.parse(await res.json());
            this._deployments.set(newDeployment.id, newDeployment);
            return newDeployment;
        }
        throw new Error("Failed to update deployment!");
    }
    public async create(deployment: PartialDeployment) {
        const res = await fetch("./api/deployment", {
            method: "post",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(deployment)
        });
        if (res.ok) {
            const newDeployment = FullDeploymentModel.parse(await res.json());
            this._deployments.set(newDeployment.id, newDeployment);
            return newDeployment;
        }
        throw new Error("Failed to create deployment!");
    }
}