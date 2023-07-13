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
export type ConnectResult = false | true | string;

export interface Node {
    getId: () => string;
    getName: () => string;
    setPosition: (x: number, y: number) => void;
    getPosition: () => { x: number, y: number };
    getConnectionGroups: () => ConnectionGroup[];
    connect: (inputId: string, outputConnection?: Connection) => ConnectResult;
    onUpdated?: (cb: () => void) => void;
}
