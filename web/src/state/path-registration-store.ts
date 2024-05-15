import { action, computed, makeObservable, observable } from "mobx";
import { PathRegistration, PathRegistrationFrontend } from "../types/path";

export class PathRegistrationStore {
    public pathRegitrations: PathRegistration[] = [];

    public get frontendPathRegistrations() {
        return this.pathRegitrations.filter(p => "frontend" in p) as PathRegistrationFrontend[];
    }

    constructor() {
        makeObservable(this, {
            pathRegitrations: observable,
            loadAll: action,
            frontendPathRegistrations: computed
        });
    }

    public async loadAll() {
        this.pathRegitrations = await fetch("./api/path-registrations").then(res => res.json())
    }
}