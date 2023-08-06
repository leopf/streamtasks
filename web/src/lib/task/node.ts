import cloneDeep from "clone-deep";
import { Connection, Node } from "../node-editor";
import { Task, TaskOutputStream } from "./types";
import { connectionToOutputStream, streamGroupToConnectionGroup } from "./utils";
import objectPath from 'object-path';
import deepEqual from "deep-equal";

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

export interface RPCTaskConnectRequest {
    input_id: string;
    output_stream?: TaskOutputStream;
    task: Task;
}

export interface RPCTaskConnectResponse {
    task?: Task;
    error_message?: string;
}
export interface RPCOnEditorResponse {
    task: Task;
    fields: TaskEditorField[];
}

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

    private _task: Task;
    public get task() {
        return this._task;
    }

    public get id() {
        return this._task.id;
    }

    constructor(task: Task) {
        this._task = task;
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
        const data = await this.rpcRequest<Task, RPCOnEditorResponse>("/rpc/on-editor", this.task);
        this.pushTask(data.task);
        return data.fields;
    }
    public async connect(inputId: string, outputConnection?: Connection): Promise<boolean | string> {
        try {
            const stream = outputConnection ? connectionToOutputStream(outputConnection) : undefined;
            const data = await this.rpcRequest<RPCTaskConnectRequest, RPCTaskConnectResponse>("/rpc/connect", {
                input_id: inputId,
                output_stream: stream,
                task: this.task,
            });

            if (data.error_message) {
                return data.error_message;
            }
            else if (data.task) {
                this.setInputTopicId(inputId, stream?.topic_id);
                this.pushTask(data.task);
            }
            else {
                return "Task did not respond with a task."
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

    private async rpcRequest<I, O>(path: string, body: I) : Promise<O> {
        const res = await fetch(`/task-factory/${this.task.task_factory_id}${path}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            throw new Error("Request failed");
        }

        return await res.json() as O;
    }
    private emitUpdated() {
        console.log("TaskNode: emitUpdated");
        this.updateHandlers.forEach(cb => cb());
    }
    private pushTask(task: Task) {
        const requiresUpdate = taskRequiresUpdate(this.task, task);
        Object.assign(this.task, task);
        if (requiresUpdate) {
            this.emitUpdated();
        }
    }
    private setInputTopicId(inputId: string, topicId?: string) {
        const taskStream = this._task.stream_groups.flatMap(g => g.inputs).find(i => i.ref_id === inputId);
        if (taskStream) {
            taskStream.topic_id = topicId;
            if (taskStream.topic_id === undefined) {
                delete taskStream.topic_id;
            }
        }
    }
}