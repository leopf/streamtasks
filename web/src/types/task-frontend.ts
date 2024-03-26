import { TaskInstance } from "./task";

export interface TaskInstanceFrontendConfig {

}

export interface StoredTaskInstance extends TaskInstance {
    frontendConfig: TaskInstanceFrontendConfig;
}
