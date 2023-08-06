import cloneDeep from "clone-deep";
import { Connection, Node } from "../node-editor";
import { Task, TaskOutputStream } from "./types";
import { connectionToOutputStream, streamGroupToConnectionGroup } from "./utils";
import objectPath from 'object-path';
import deepEqual from "deep-equal";

export interface RPCTaskConnectRequest {
    input_id: string;
    output_stream?: TaskOutputStream;
    task: Task;
}

export interface RPCTaskConnectResponse {
    task?: Task;
    error_message?: string;
}
export type TaskEditorFieldBase<T extends string> = {
    type: T;
    label: string;
}
export type TaskEditorInputField<T extends string> = TaskEditorFieldBase<T> & {
    config_path: string;
    valid: boolean;
}
export type TaskEditorTextField = TaskEditorInputField<"text">;
export type TaskEditorSelectField = TaskEditorInputField<"select"> & {
    options: ({ label: string, value: any })[];
}
export type TaskEditorHeaderField = TaskEditorFieldBase<"header">;
export type TaskEditorField = TaskEditorTextField | TaskEditorSelectField | TaskEditorHeaderField;

function taskRequiresUpdate(oldTask: Task, newTask: Task) {
    const updatePaths = [
        "config.label",
        "config.position",
        "stream_groups",
    ];

    return updatePaths.some(path => !deepEqual(objectPath(oldTask).get(path), objectPath(newTask).get(path)));
}

export class TaskNode implements Node {
    private updateHandlers = new Set<(() => void)>();
    
    public task: Task;

    public get id() {
        return this.task.id;
    }

    constructor(task: Task) {
        this.task = task;
    }

    public getId() {
        return this.task.id;
    }
    public getName() {
        return this.task.config.label || "[no name]"
    }
    public setPosition(x: number, y: number) {
        this.task.config.position = { x, y };
    }
    public getPosition() {
        return this.task.config.position ?? { x: 0, y: 0 };
    }
    public setConfig(path: string, value: any) {
        objectPath(this.task).set(path, value);
    }
    public getConfig(path: string, defaultValue?: any) {
        return objectPath(this.task).get(path, defaultValue);
    }
    public getConnectionGroups() {
        return this.task.stream_groups.map(streamGroupToConnectionGroup);
    }
    public async getEditorFields(): Promise<TaskEditorField[]> {
        await new Promise(resolve => setTimeout(resolve, 1000));
        return [
            {
                type: "header",
                label: "General"
            },
            {
                type: "text",
                label: "Formula",
                config_path: "formula_input",
                valid: true,
            },
            {
                type: "select",
                label: "Encoding",
                config_path: "encoding",
                options: [
                    { label: "h264", value: "h264" },
                    { label: "h265", value: "h265" },
                ],
                valid: true,
            }
        ];
    }
    public async connect(inputId: string, outputConnection?: Connection): Promise<boolean | string> {
        try {
            const stream = outputConnection ? connectionToOutputStream(outputConnection) : undefined;

            const res = await fetch(`/task-factory/${this.task.task_factory_id}/rpc/connect`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(<RPCTaskConnectRequest>{
                    input_id: inputId,
                    output_stream: stream,
                    task: this.task,
                })
            });

            if (!res.ok) {
                return false;
            }

            const data = await res.json() as RPCTaskConnectResponse;
            if (data.error_message) {
                return data.error_message;
            }
            else if (data.task) {
                const cloned = cloneDeep(this.task);
                cloned.stream_groups.forEach(group => {
                    group.inputs.forEach(input => {
                        if (input.ref_id === inputId) {
                            input.topic_id = stream?.topic_id;
                            if (input.topic_id === undefined) {
                                delete input.topic_id;
                            }
                        }
                    });
                });

                Object.assign(this.task, data.task);
                if (taskRequiresUpdate(cloned, data.task)) {
                    console.log("update")
                    this.updateHandlers.forEach(cb => cb());
                }
            }
            else {
                return "Error while creating the connection."
            }
        }
        catch (e) {
            return String(e);
        }

        return true;
    }

    public onUpdated(cb: () => void) {
        this.updateHandlers.add(cb);
    }
    public offUpdated(cb: () => void) {
        this.updateHandlers.delete(cb);
    }
}