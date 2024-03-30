export interface Connection {
    refId: string;
    label: string;
    config: Record<string, any>;
}

export interface InputConnection extends Connection {
    linkedStreamId?: string;
}

export type ConnectResult = boolean | string;

export interface Node {
    id: string;
    name: string;
    position: { x: number, y: number };
    outputs: Connection[];
    inputs: InputConnection[];
    connect: (inputId: string, outputConnection?: Connection) => Promise<ConnectResult>;
    onUpdated?: (cb: () => void) => void;
}

export type NodeDisplayOptions = {
    padding?: number;
    backgroundColor?: string;
    disableAutoResize?: boolean;
}

export type NodeRenderOptions = ({ width: number, height?: never } | { height: number, width?: never }) & NodeDisplayOptions;