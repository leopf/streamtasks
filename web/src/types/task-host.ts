import { z } from "zod";
import { TaskHostDragDataModel } from "../model/task-host";

export type TaskHostDragData = z.infer<typeof TaskHostDragDataModel>;
