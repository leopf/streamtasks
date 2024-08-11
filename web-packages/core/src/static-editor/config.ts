import { createContext, useContext } from "react";

export interface StaticEditorConfig {
    DynamicSelect: { baseUrl: string }
    Secret: { baseUrl: string }
}

export const StaticEditorConfigContext = createContext<Partial<StaticEditorConfig>>({});

export function useStaticEditorConfig(): StaticEditorConfig {
    const ctx = useContext(StaticEditorConfigContext);
    const defaultUrl = String(new URL("./", location.href))

    return {
        DynamicSelect: { baseUrl: ctx.DynamicSelect?.baseUrl ?? defaultUrl },
        Secret: { baseUrl: ctx.Secret?.baseUrl ?? defaultUrl }
    };
}