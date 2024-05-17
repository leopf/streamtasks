import { z } from "zod";
import { DashboardModel, DashboardWindowModel } from "../model/dashboard";

export type DashboardWindow = z.infer<typeof DashboardWindowModel>;
export type Dashboard = z.infer<typeof DashboardModel>;