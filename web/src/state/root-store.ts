import { createStateContext } from "./util";
import { DeploymentStore } from "./deployment-store";
import { UIControlStore } from "./ui-control-store";
import { TaskManager } from "./task-manager";
import { TaskStore } from "./task-store";

export class RootStore {
    public deployment = new DeploymentStore(this);
    public task = new TaskStore();
    public uiControl = new UIControlStore();
    public taskManager = new TaskManager();
}

export const [ RootStoreContext, useRootStore ] = createStateContext<RootStore>();