import { z } from "zod";
import { MetadataModel, TaskOutputModel, TaskInputModel, TaskModel, TaskHostModel, TaskFrontendConfigModel, FullTaskModel, TaskInstanceModel, StoredTaskModel, TaskPartialInputModel } from "../model/task";

export type Metadata = z.infer<typeof MetadataModel>;
export type TaskOutput = z.infer<typeof TaskOutputModel>;
export type TaskInput = z.infer<typeof TaskInputModel>;
export type TaskPartialInput = z.infer<typeof TaskPartialInputModel>;
export type Task = z.infer<typeof TaskModel>;
export type RunningTask = Task & { taskInstance: TaskInstance };
export type StoredTask = z.infer<typeof StoredTaskModel>;
export type FullTask = z.infer<typeof FullTaskModel>;
export type TaskFrontendConfig = z.infer<typeof TaskFrontendConfigModel>;
export type TaskInstance = z.infer<typeof TaskInstanceModel>;
export type TaskHost = z.infer<typeof TaskHostModel>;
export type TaskDisplayOptions = { context: "task" | "dashboard" };
export type TaskConfiguratorContext = { taskHost: TaskHost, idGenerator: () => number }

export interface TaskConfigurator {
    create: (context: TaskConfiguratorContext) => (Task | Promise<Task>);
    connect: (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => (Task | Promise<Task>);
    // the editor can dispatch an event on element (or bubble it) with the name "task-instance-updated" to tell the system the instance has updated
    renderEditor?: (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => void;  
    renderDisplay?: (task: RunningTask, element: HTMLElement, options: TaskDisplayOptions, context: TaskConfiguratorContext) => void;  
}

export interface TaskIO {
    inputs: TaskInput[];
    outputs: TaskOutput[];
}

export enum TaskInstanceStatus {
    scheduled = "scheduled",
    running = "running",
    stopped = "stopped",
    ended = "ended",
    failed = "failed",
}