import { z } from "zod";
import { EditorField } from "./types";

export function getConfigModelByFields(fields: EditorField[]) {
    const model: Record<string, z.ZodType> = {};
    for (const field of fields) {
        if (field.type === "select") {
            model[field.key] = z.union(field.items.map(item => z.literal(item.value)) as any);
        }
        else if (field.type === "boolean") {
            model[field.key] = z.boolean()
        }
        else if (field.type === "number") {
            let f = z.number();
            if (field.integer) f = f.int();
            if (field.max !== undefined) f = f.max(field.max);
            if (field.min !== undefined) f = f.min(field.min);
            model[field.key] = f;
        }
    }
    return z.object(model);
}