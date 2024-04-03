import { z } from "zod";
import { DeploymentModel, PartialDeploymentModel } from "../model/deployment";

export type PartialDeployment = z.infer<typeof PartialDeploymentModel>;
export type Deployment = z.infer<typeof DeploymentModel>;