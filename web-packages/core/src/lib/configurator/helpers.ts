import { z } from "zod";
import { Metadata } from "../../types/task";

export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: true): O;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: false): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force?: boolean) {
    let rawData: any = metadata[key]
    try {
        rawData = JSON.parse(String(rawData));
    }  
    catch {}
    if (rawData === undefined) {
        if (force) {
            throw new Error(`Field "${key}" not defined!`);
        }
        return undefined;
    }
    if (force) {
        return model.parse(rawData)
    }
    else {
        const res = model.safeParse(rawData);
        if (res.success) {
            return res.data;
        }
        return undefined;
    }
}

export function extractObjectPathValues(data: any, prefix: string = "", result?: Map<string, any>) {
    result = result ?? new Map();
    // TODO: fix recursion
    if (typeof data == "object" && data !== null) {
        if (Array.isArray(data)) {
            data.forEach((v, idx) => extractObjectPathValues(v, prefix + idx + ".", result));
        }
        else {
            Object.entries(data).forEach(([k, v]) => extractObjectPathValues(v, prefix + k + ".", result))
        }
    }
    else {
        result.set(prefix.substring(0, prefix.length - 1), data);
    }
    return result;
}