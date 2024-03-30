import { TaskInstance } from "./task";

export type TaskInstanceFrontendConfig = Partial<{
    position: { x: number, y: number };
}>;

export interface StoredTaskInstance extends TaskInstance {
    frontendConfig?: TaskInstanceFrontendConfig;
}
