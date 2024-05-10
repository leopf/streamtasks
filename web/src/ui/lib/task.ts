import { useEffect, useReducer } from "react";
import { ManagedTask } from "../../lib/task";

export function useTaskUpdate(task: ManagedTask, handler: () => void, updateComponent: boolean = false) {
    const [updateCount, forceUpdate] = useReducer(x => x + 1, 0);
    const innerHandler = () => {
        handler();
        if (updateComponent) {
            forceUpdate();
        }
    };
    useEffect(() => {
        task.on("updated", innerHandler);
        task.on("connected", innerHandler);
        return () => {
            task.off("updated", innerHandler);
            task.off("connected", innerHandler);
        }
    }, [task]);
    return updateCount;
}