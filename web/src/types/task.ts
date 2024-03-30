import { z } from "zod";
import { MetadataModel, TaskOutputModel, TaskInputModel, TaskInstanceModel, TaskHostModel } from "../model/task";

export type Metadata = z.infer<typeof MetadataModel>;
export type TaskOutput = z.infer<typeof TaskOutputModel>;
export type TaskInput = z.infer<typeof TaskInputModel>;
export type TaskInstance = z.infer<typeof TaskInstanceModel>;
export type TaskHost = z.infer<typeof TaskHostModel>;

export type TaskConfiguratorContext = { taskHost: TaskHost, idGenerator: () => number }

export interface TaskConfigurator {
    create: (context: TaskConfiguratorContext) => (TaskInstance | Promise<TaskInstance>);
    connect: (taskInstance: TaskInstance, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => (TaskInstance | Promise<TaskInstance>);
    // the editor can dispatch an event on element (or bubble it) with the name "task-instance-updated" to tell the system the instance has updated
    renderEditor?: (taskInstance: TaskInstance, element: HTMLElement, context: TaskConfiguratorContext) => void;
   
    // TODO: I think we can do better, should be on the server
    toStartConfig?: (taskInstance: TaskInstance, context: TaskConfiguratorContext) => (any | Promise<any>);
    remapTopicIds?: (taskInstance: TaskInstance, idMap: Map<number, number>, context: TaskConfiguratorContext) => (TaskInstance | Promise<TaskInstance>);
}

export interface TaskIO {
    inputs: TaskInput[];
    outputs: TaskOutput[];
}