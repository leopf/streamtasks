import { createStateContext } from "./util";
import { DeploymentStore } from "./deployment-store";
import { UIControlStore } from "./ui-control-store";
import { TaskManager } from "./task-manager";
import { TaskStore } from "./task-store";
import { PathRegistrationStore } from "./path-registration-store";
import { DashboardStore } from "./dashboard-store";

export class RootStore {
    public deployment = new DeploymentStore(this);
    public task = new TaskStore();
    public dashboard = new DashboardStore();
    public uiControl = new UIControlStore();
    public taskManager = new TaskManager();
    public pathRegistration = new PathRegistrationStore();

    public async init() {
        await this.taskManager.init()
        await this.deployment.loadAll();
        await this.pathRegistration.loadAll();
    }
}

export const [ RootStoreContext, useRootStore ] = createStateContext<RootStore>();