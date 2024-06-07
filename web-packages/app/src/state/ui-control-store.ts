import { makeObservable, observable } from "mobx";
import { v4 as uuidv4 } from "uuid";
import { Dashboard } from "../types/dashboard";
import { Deployment, PartialDeployment } from "../types/deployment";
import { Topic } from "../types/topic";

export class UIControlStore {
    public selectedTopic?: Topic = undefined;
    public editingDeployment?: Deployment | PartialDeployment = undefined;
    public editingDashboard?: Dashboard = undefined;

    constructor() {
        makeObservable(this, {
            editingDeployment: observable,
            editingDashboard: observable,
            selectedTopic: observable
        })
    }

    public createNewDashboard(deploymentId: string) {
        this.editingDashboard = { label: "New Dashboard", id: uuidv4(), deployment_id: deploymentId, windows: [] }
    }
    public editDashboard(d: Dashboard) {
        this.editingDashboard = d;
    }
    public createNewDeployment() {
        this.editingDeployment = { label: "New Deployment" }
    }
    public editDeployment(d: PartialDeployment | Deployment) {
        this.editingDeployment = d;
    }
    public closeDeploymentEditor() {
        this.editingDeployment = undefined;
    }
    public closeDashboardEditor() {
        this.editingDashboard = undefined;
    }
}
