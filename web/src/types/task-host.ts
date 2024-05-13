import { z } from "zod";
import { TaskHostDragDataModel } from "../model/task-host";

export type TaskHostDragData = z.infer<typeof TaskHostDragDataModel>;

export interface ParsedTaskHost {
    id: string,
    label: string;
    nodeName?: string;
    tags: string[];
    description?: string;
    configurator?: string;
}