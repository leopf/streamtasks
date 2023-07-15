import { z } from "zod";
import { PointModel } from "../../model";
import { Connection, ConnectionGroup, InputConnection, Node } from "../node-editor";
import { TaskStreamGroup, Task, TaskOutputStream, TaskStreamBase } from "./types";
import { v4 as uuidv4 } from 'uuid';
import cloneDeep from "clone-deep";

export function connectionToOutputStream(connection: Connection): TaskOutputStream {
    return {
        label: connection.label,
        content_type: connection.config.contentType,
        encoding: connection.config.encoding,
        extra: connection.config.extra,
        topic_id: connection.refId
    }
}

export function cloneTask(task: Task): Task {
    const newTask = cloneDeep(task);
    newTask.id = uuidv4();
    newTask.stream_groups.forEach(group => {
        group.inputs.forEach(input => {
            input.ref_id = uuidv4();
        });
        group.outputs.forEach(output => {
            output.topic_id = uuidv4();
        });
    });
    return newTask;
}

export function streamGroupToConnectionGroup(group: TaskStreamGroup): ConnectionGroup {
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

export function taskToDisplayNode(task: Task): Node {
    return {
        connect: async () => false,
        getId: () => task.id,
        getName: () => task.config.label,
        getPosition: () => ({ x: 0, y: 0 }),
        setPosition: () => { },
        getConnectionGroups: () => task.stream_groups.map(streamGroupToConnectionGroup),
    };
}

export function streamToString(stream: TaskStreamBase): string {
    const format = [stream.content_type, stream.encoding].filter(x => x).join('/');
    if (format) {
        return `${stream.label} (${format})`;
    }
    else {
        return stream.label;
    }
}
