import { z } from "zod";

export const TextFieldModel = z.object({
    type: z.literal("text"),
    label: z.string(),
    key: z.string(),
});
export const NumberFieldModel = z.object({
    type: z.literal("number"),
    label: z.string(),
    key: z.string(),
    min: z.number().optional(),
    max: z.number().optional(),
    unit: z.string().optional(),
    integer: z.boolean().default(false),
});
export const SelectFieldModel = z.object({
    type: z.literal("select"),
    label: z.string(),
    key: z.string(),
    items: z.array(z.object({
        value: z.union([z.string(), z.number()]),
        label: z.string()
    }))
});
export const BooleanFieldModel = z.object({
    type: z.literal("boolean"),
    label: z.string(),
    key: z.string()
});
export const EditorFieldModel = z.discriminatedUnion("type", [NumberFieldModel, SelectFieldModel, BooleanFieldModel, TextFieldModel])

export type TextField = z.infer<typeof TextFieldModel>;
export type NumberField = z.infer<typeof NumberFieldModel>;
export type SelectField = z.infer<typeof SelectFieldModel>;
export type BooleanField = z.infer<typeof BooleanFieldModel>;

export type EditorField = z.infer<typeof EditorFieldModel>;
