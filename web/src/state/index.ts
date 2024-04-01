import { createContext, useContext } from "react";
import { TaskManager } from "./task-manager";
import { DeploymentState } from "./deployment";

export const GlobalStateContext = createContext<{ 
    taskManager: TaskManager,
    deployment?: DeploymentState
} | undefined>(undefined);
export function useGlobalState() {
    const globalState = useContext(GlobalStateContext)
    if (!globalState) {
        throw new Error("Global state not provided by context!");
    }
    return globalState;
}