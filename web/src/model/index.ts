import { z } from "zod";

export const PointModel = z.object({
    x: z.number(),
    y: z.number(),
});
export type Point = z.infer<typeof PointModel>;