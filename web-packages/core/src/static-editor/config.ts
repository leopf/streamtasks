import { createContext, useContext } from "react";

export interface StaticEditorConfig {
    baseUrl: string
}

export const StaticEditorConfigContext = createContext<Partial<StaticEditorConfig>>({});

export function useStaticEditorConfig(): StaticEditorConfig {
    const ctx = useContext(StaticEditorConfigContext);
    return {
        baseUrl: ctx.baseUrl ?? location.href
    };
}