import { z } from "zod";
import { EditorField } from "./types";

export function getConfigModelByFields(fields: EditorField[]) {
    const model: Record<string, z.ZodType> = {};
    for (const field of fields) {
        if (field.type === "select") {
            model[field.key] = z.union(field.items.map(item => z.literal(item.value)) as any);
        }
        else if (field.type === "multiselect") {
            const keys = Object.keys(field.items[0]);
            for (const key of keys) {
                model[key] = z.union(Array.from(new Set(field.items.map(item => item[key]))).map(item => z.literal(item)) as any);
            }
        }
        else if (field.type === "boolean") {
            model[field.key] = z.boolean();
        }
        else if (field.type === "number") {
            let f = z.number();
            if (field.integer) f = f.int();
            if (field.max !== undefined) f = f.max(field.max);
            if (field.min !== undefined) f = f.min(field.min);
            model[field.key] = f;
        }
        else if (field.type === "slider") {
            model[field.key] = z.number().min(field.min).max(field.max);
        }
        else if (field.type === "kvoptions") {
            model[field.key] = z.record(z.string(), z.string());
        }
        else if (field.type === "text") {
            model[field.key] = z.string();
        }
    }
    return model;
}