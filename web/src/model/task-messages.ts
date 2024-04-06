import { z } from "zod";
import { TaskInstanceModel } from "./task";

export const UpdateTaskInstanceMessageModel = z.object({
    id: z.string().uuid(),
    task_instance: TaskInstanceModel
});