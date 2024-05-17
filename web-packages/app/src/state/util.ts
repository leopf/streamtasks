import { createContext, Context, useContext } from "react";

const throwContextNotFound = () => {throw new Error("Context not found!")}; 

export function createStateContext<T>(): [ Context<T | undefined>, () => T ] {
    const ctx = createContext<T | undefined>(undefined);
    return [
        ctx,
        () => useContext(ctx) ?? throwContextNotFound()
    ];
}