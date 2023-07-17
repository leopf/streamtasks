import { z } from "zod";

export const PointModel = z.object({
    x: z.number(),
    y: z.number(),
});
export type Point = z.infer<typeof PointModel>;

export const LogEntryModel = z.object({
    id: z.string().uuid(),
    level: z.string(),
    message: z.string(),
    timestamp: z.coerce.date(),
});

export type LogEntry = z.infer<typeof LogEntryModel>;