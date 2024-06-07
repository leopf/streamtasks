import { z } from "zod";
import { TaskInstanceStatus } from "../types";

export const MetadataModel = z.record(z.string(), z.union([ z.number(), z.string(), z.boolean(), z.undefined() ])) 
export const TaskOutputModel = MetadataModel.and(z.object({
    topic_id: z.number()
}));
export const TaskInputModel = MetadataModel.and(z.object({
    topic_id: z.number().optional(),
    key: z.string()
}));
export const TaskPartialInputModel = MetadataModel.and(z.object({
    key: z.string()
}));
export const TaskModel = z.object({
    id: z.string().uuid(),
    task_host_id: z.string(),
    label: z.string(),
    config: z.record(z.string(), z.any()),
    inputs: z.array(TaskInputModel),
    outputs: z.array(TaskOutputModel),
});
export const TaskFrontendConfigModel = z.object({
    position: z.object({ x: z.number(), y: z.number() }).optional()
})
export const TaskInstanceModel = z.object({
    id: z.string().uuid(),
    host_id: z.string(),
    topic_space_id: z.number().int().optional().nullable(),
    metadata: MetadataModel,
    error: z.string().optional().nullable(),
    status:  z.nativeEnum(TaskInstanceStatus),
});
export const StoredTaskModel = TaskModel.extend({
    frontend_config: TaskFrontendConfigModel
})
export const FullTaskModel = StoredTaskModel.extend({
    task_instance: TaskInstanceModel.optional().nullable(),
});

export const TaskHostModel = z.object({
    id: z.string(),
    metadata: MetadataModel
});

