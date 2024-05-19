import { z } from "zod";
import { EditorField } from "./types";

export function getFieldValidator(field: EditorField) {
    if (field.type === "select") {
        return z.union(field.items.map(item => z.literal(item.value)) as any);
    }
    else if (field.type === "boolean") {
        return z.boolean();
    }
    else if (field.type === "number") {
        let f = z.number();
        if (field.integer) f = f.int();
        if (field.max !== undefined) f = f.max(field.max);
        if (field.min !== undefined) f = f.min(field.min);
        return f;
    }
    else if (field.type === "slider") {
        return z.number().min(field.min).max(field.max);
    }
    else if (field.type === "kvoptions") {
        return z.record(z.string(), z.string());
    }
    else if (field.type === "text") {
        return z.string();
    }
    throw new Error("No validator for field!");
}

export function getConfigModelByFields(fields: EditorField[]) {
    const model: Record<string, z.ZodType> = {};
    for (const field of fields) {
        model[field.key] = getFieldValidator(field);
    }
    return z.object(model);
}