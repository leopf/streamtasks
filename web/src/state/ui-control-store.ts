import { makeObservable, observable } from "mobx";
import { Deployment, PartialDeployment } from "../types/deployment";
import { Topic } from "../types/topic";
import { createStateContext } from "./util";

export class UIControlStore {
    public selectedTopic?: Topic = undefined;
    public editingDeployment?: Deployment | PartialDeployment = undefined;

    constructor() {
        makeObservable(this, {
            editingDeployment: observable,
            selectedTopic: observable
        })
    }

    public createNewDeployment() {
        this.editingDeployment = { label: "New Deployment" }
    }
}

export const [ UIControlContext, useUIControl ] = createStateContext<UIControlStore>();