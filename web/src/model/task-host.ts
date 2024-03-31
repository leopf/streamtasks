import { z } from "zod";

export const TaskHostDragDataModel = z.object({
    ox: z.number(),
    oy: z.number(),
    id: z.string()
}) 
