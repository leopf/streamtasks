import { createContext, useContext } from "react";
import { TaskManager } from "./task-manager";

export const GlobalStateContext = createContext<{ taskManager: TaskManager } | undefined>(undefined);
export function useGlobalState() {
    const globalState = useContext(GlobalStateContext)
    if (!globalState) {
        throw new Error("Global state not provided by context!");
    }
    return globalState;
}