export interface Connection {
    refId: string;
    label: string;
    config: Record<string, any>;
}

export interface InputConnection extends Connection {
    linkedStreamId?: string;
}

export interface ConnectionGroup {
    outputs: Connection[];
    inputs: InputConnection[];
}

export interface Point {
    x: number;
    y: number;
}

export type ConnectResult = false | true | string;

export interface Node {
    id: string;
    getName: () => string;
    setPosition: (x: number, y: number) => void;
    getPosition: () => { x: number, y: number };
    getConnectionGroups: () => ConnectionGroup[];
    connect: (inputId: string, outputConnection?: Connection) => ConnectResult;
    onUpdated?: (cb: () => void) => void;
}
