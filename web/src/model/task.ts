import { z } from "zod";

export const MetadataModel = z.record(z.string(), z.union([ z.number(), z.string(), z.boolean() ])) 
export const TaskOutputModel = MetadataModel.and(z.object({
    topic_id: z.number()
}));
export const TaskInputModel = MetadataModel.and(z.object({
    topic_id: z.number().optional(),
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
export const StoredTaskModel = TaskModel.extend({
    frontendConfig: TaskFrontendConfigModel.optional()
});
export const TaskHostModel = z.object({
    id: z.string(),
    metadata: MetadataModel
});

