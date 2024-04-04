import { z } from "zod";
import { MetadataModel, TaskOutputModel, TaskInputModel, TaskModel, TaskHostModel, StoredTaskModel, TaskFrontendConfigModel } from "../model/task";

export type Metadata = z.infer<typeof MetadataModel>;
export type TaskOutput = z.infer<typeof TaskOutputModel>;
export type TaskInput = z.infer<typeof TaskInputModel>;
export type Task = z.infer<typeof TaskModel>;
export type StoredTask = z.infer<typeof StoredTaskModel>;
export type TaskFrontendConfig = z.infer<typeof TaskFrontendConfigModel>;
export type TaskHost = z.infer<typeof TaskHostModel>;

export type TaskConfiguratorContext = { taskHost: TaskHost, idGenerator: () => number }

export interface TaskConfigurator {
    create: (context: TaskConfiguratorContext) => (Task | Promise<Task>);
    connect: (taskInstance: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => (Task | Promise<Task>);
    // the editor can dispatch an event on element (or bubble it) with the name "task-instance-updated" to tell the system the instance has updated
    renderEditor?: (taskInstance: Task, element: HTMLElement, context: TaskConfiguratorContext) => void;
   
    // TODO: I think we can do better, should be on the server
    toStartConfig?: (taskInstance: Task, context: TaskConfiguratorContext) => (any | Promise<any>);
    remapTopicIds?: (taskInstance: Task, idMap: Map<number, number>, context: TaskConfiguratorContext) => (Task | Promise<Task>);
}

export interface TaskIO {
    inputs: TaskInput[];
    outputs: TaskOutput[];
}