import { useEffect, useReducer } from "react";
import { ManagedTask, TaskInstanceStatus } from "@streamtasks/core";
import { GeneralStatus } from "../types/status";

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

export function ioFieldNameToLabel(fieldName: string) {
    return fieldName.replaceAll("_", " ")
}
export function ioFieldValueToText(key: string, value: any) {
    if (key === "type" && value === "ts") {
        return "timestamp"
    }
    return String(value)
}

export const ioMetadataHideKeys = new Set([ "key" ]);

export const taskInstance2GeneralStatusMap: Record<TaskInstanceStatus, GeneralStatus> = {
    ended: "passive",
    failed: "error",
    stopped: "passive",
    scheduled: "passive",
    running: "ok",
};