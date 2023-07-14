import { z } from "zod";
import { PointModel } from "../../model";
import { Connection, ConnectionGroup, InputConnection, Node } from "../node-editor";
import { TaskStream, TaskStreamGroup, Task, TaskNode } from "./types";

function streamFromConnection(connection: Connection): TaskStream {
    return {
        label: connection.label,
        content_type: connection.config.contentType,
        encoding: connection.config.encoding,
        extra: connection.config.extra,
        topic_id: connection.refId
    }
}

function streamGroupToConnectionGroup(group: TaskStreamGroup): ConnectionGroup {
    return {
        inputs: group.inputs.map(input => (<InputConnection>{
            refId: input.ref_id,
            label: input.label,
            linkedStreamId: input.topic_id ?? undefined,
            config: {
                contentType: input.content_type,
                encoding: input.encoding,
                extra: input.extra,
            }
        })),
        outputs: group.outputs.map(output => (<Connection>{
            refId: output.topic_id,
            label: output.label,
            config: {
                contentType: output.content_type,
                encoding: output.encoding,
                extra: output.extra,
            }
        })),
    }
}

export function taskToTemplateNode(task: Task): Node {
    return {
        connect: () => false,
        getId: () => task.id,
        getName: () => task.config.label,
        getPosition: () => ({ x: 0, y: 0 }),
        setPosition: () => { },
        getConnectionGroups: () => task.stream_groups.map(streamGroupToConnectionGroup),
    };
}

export function streamToString(stream: TaskStream): string {
    const format = [stream.content_type, stream.encoding].filter(x => x).join('/');
    if (format) {
        return `${stream.label} (${format})`;
    }
    else {
        return stream.label;
    }
}

export function taskToMockNode(task: Task): Node {
    return {
        getId: () => task.id,
        getName: () => task.config.label,
        getPosition: () => task.config.position ?? ({ x: 0, y: 0 }),
        setPosition: (x, y) => { task.config.position = { x, y } },
        connect: (inputId, connection) => {
            for (const group of task.stream_groups) {
                for (const input of group.inputs) {
                    if (input.ref_id === inputId) {
                        input.topic_id = connection?.refId ?? "";
                        return true;
                    }
                }
            }
            return false;
        },
        getConnectionGroups: () => task.stream_groups.map(streamGroupToConnectionGroup),
    };
}

export function wrapTaskInNode(task: TaskNode): Node {
    return {
        getId: () => task.getId(),
        getName: () => {
            const nameRes = z.string().safeParse(task.getConfig('label'))
            if (nameRes.success) {
                return nameRes.data;
            }
            else {
                return '<unnamed>';
            }
        },
        connect: (inputId: string, outputConnection?: Connection) => {
            return task.connect(inputId, outputConnection ? streamFromConnection(outputConnection) : undefined);
        },
        onUpdated: task.onUpdated,
        getPosition: () => {
            const pos = PointModel.safeParse(task.getConfig('position'));
            if (pos.success) {
                return pos.data;
            }
            else {
                return { x: 0, y: 0 };
            }
        },
        setPosition: (x: number, y: number) => task.setConfig('position', { x, y }),
        getConnectionGroups: () => task.getStreamGroups().map(streamGroupToConnectionGroup)
    }
}