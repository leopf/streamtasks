export interface TaskStreamBase {
    label: string;
    content_type?: string;
    encoding?: string;
    extra?: Record<string, string | number | boolean>;
}

export interface TaskOutputStream extends TaskStreamBase {
    topic_id: string;
}

export interface TaskInputStream extends TaskStreamBase {
    ref_id: string;
    topic_id?: string;
}

export type TaskStream = TaskInputStream | TaskOutputStream;

export interface TaskStreamGroup {
    inputs: TaskInputStream[];
    outputs: TaskOutputStream[];
}

export interface Task {
    id: string;
    task_factory_id: string;
    config: Record<string, any>;
    status?: string;
    error?: string;
    stream_groups: TaskStreamGroup[];
}

export type DeploymentStatus = 'offline' | 'starting' | 'running' | 'stopping' | 'failing' | 'failed';

export interface DeploymentBase {
    id: string;
    label: string;
}

export interface Deployment extends DeploymentBase {
    status: DeploymentStatus;
    tasks: Task[];
}
