export interface TaskStream {
    label: string;
    topic_id: string;
    content_type?: string;
    encoding?: string;
    extra?: Record<string, string | number | boolean>;
}

export interface TaskInputStream extends TaskStream {
    ref_id: string;
}

export interface TaskStreamGroup {
    inputs: TaskInputStream[];
    outputs: TaskStream[];
}

export interface Task {
    id: string;
    task_factory_id: string;
    config: Record<string, any>;
    status?: string;
    error?: string;
    stream_groups: TaskStreamGroup[];
}

export interface Deployment {
    tasks: Task[];
    id: string;
    label: string;
    status: "offline" | "running" | "error";
}

export interface TaskNode {
    getId: () => string;
    setConfig: (key: string, value: any) => void;
    getConfig: (key: string) => any;
    getStreamGroups: () => TaskStreamGroup[];
    onUpdated?: (cb: () => void) => void;
    connect: (inputRefId: string, stream?: TaskStream) => boolean | string;
}