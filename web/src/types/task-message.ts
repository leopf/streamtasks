import { z } from "zod";
import { UpdateTaskInstanceMessageModel } from "../model/task-messages";

export type UpdateTaskInstanceMessage = z.infer<typeof UpdateTaskInstanceMessageModel>;