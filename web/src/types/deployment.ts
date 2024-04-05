import { z } from "zod";
import { DeploymentModel, FullDeploymentModel, PartialDeploymentModel } from "../model/deployment";

export type PartialDeployment = z.infer<typeof PartialDeploymentModel>;
export type Deployment = z.infer<typeof DeploymentModel>;
export type FullDeployment = z.infer<typeof FullDeploymentModel>;