export type Connection = { id: string | number, label?: string } & Record<string, string | boolean | number>;
export type OutputConnection = { streamId: number,  } & Connection;
export type InputConnection = { key: string, streamId?: number} & Connection;

export type ConnectResult = boolean | string;

export interface Node {
    id: string;
    label: string;
    host: string | undefined;
    statusColor?: string;
    position: { x: number, y: number };
    outputs: OutputConnection[];
    inputs: InputConnection[];
    connect: (key: string, output?: OutputConnection) => Promise<ConnectResult>;
    on?: (name: "updated", cb: () => void) => void;
    destroy?: () => void;
}

export type NodeDisplayOptions = {
    padding?: number;
    backgroundColor?: string;
    disableAutoResize?: boolean;
}

export type NodeRenderOptions = ({ width: number, height?: never } | { height: number, width?: never }) & NodeDisplayOptions;