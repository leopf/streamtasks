import { z } from "zod";


export const PartialDeploymentModel = z.object({
    label: z.string()
});
export const DeploymentModel = PartialDeploymentModel.extend({
    id: z.string().uuid()
});