import { z } from "zod";

export const DashboardWindowModel = z.object({
    task_id: z.string().uuid(),
    x: z.number(),
    y: z.number(),
    width: z.number(),
    height: z.number(),
});
export const DashboardModel = z.object({
    id: z.string().uuid(),
    deployment_id: z.string().uuid(),
    label: z.string(),
    windows: z.array(DashboardWindowModel)
})