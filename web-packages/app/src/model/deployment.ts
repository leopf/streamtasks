import { z } from "zod";


export const PartialDeploymentModel = z.object({
    label: z.string()
});
export const DeploymentModel = PartialDeploymentModel.extend({
    id: z.string().uuid(),
});
export const DeploymentStatusModel = z.union([ z.literal("running"), z.literal("scheduled"), z.literal("offline") ])
export const FullDeploymentModel = DeploymentModel.extend({
    status: DeploymentStatusModel.default("offline")
})