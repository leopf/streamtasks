import { z } from "zod";
import { DeploymentModel, DeploymentStatusModel, FullDeploymentModel, PartialDeploymentModel } from "../model/deployment";

export type PartialDeployment = z.infer<typeof PartialDeploymentModel>;
export type Deployment = z.infer<typeof DeploymentModel>;
export type DeploymentStatus = z.infer<typeof DeploymentStatusModel>;
export type FullDeployment = z.infer<typeof FullDeploymentModel>;