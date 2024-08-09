import { z } from "zod";
import { MetadataModel } from "../model";

export const TextFieldModel = z.object({
    type: z.literal("text"),
    label: z.string(),
    key: z.string(),
    multiline: z.boolean().optional()
});
export const NumberFieldModel = z.object({
    type: z.literal("number"),
    label: z.string(),
    key: z.string(),
    min: z.number().optional(),
    max: z.number().optional(),
    unit: z.string().optional(),
    integer: z.boolean().optional(),
});
export const SliderFieldModel = z.object({
    type: z.literal("slider"),
    label: z.string(),
    key: z.string(),
    min: z.number(),
    max: z.number(),
    pow: z.number()
});

export const SelectItemModel = z.object({
    value: z.union([z.string(), z.number()]),
    label: z.string()
});
export const SelectFieldModel = z.object({
    type: z.literal("select"),
    label: z.string(),
    key: z.string(),
    items: z.array(SelectItemModel)
});
export const DynamicSelectFieldModel = z.object({
    type: z.literal("dynamicselect"),
    label: z.string(),
    key: z.string(),
    path: z.string()
});
export const MultiselectFieldModel = z.object({
    type: z.literal("multiselect"),
    items: z.array(z.record(z.string(), z.union([ z.string(), z.number() ])))
});
export const BooleanFieldModel = z.object({
    type: z.literal("boolean"),
    label: z.string(),
    key: z.string()
});
export const KVOptionsFieldModel = z.object({
    type: z.literal("kvoptions"),
    label: z.string(),
    key: z.string(),
    suggestions: z.array(z.string()).optional()
});

export const EditorFieldModel = z.discriminatedUnion("type", [NumberFieldModel, SliderFieldModel, SelectFieldModel, DynamicSelectFieldModel, BooleanFieldModel, TextFieldModel, KVOptionsFieldModel, MultiselectFieldModel])
export const EditorFieldsModel = z.array(EditorFieldModel);

export type SelectItem = z.infer<typeof SelectItemModel>;
export type TextField = z.infer<typeof TextFieldModel>;
export type NumberField = z.infer<typeof NumberFieldModel>;
export type SliderField = z.infer<typeof SliderFieldModel>;
export type SelectField = z.infer<typeof SelectFieldModel>;
export type DynamicSelectField = z.infer<typeof DynamicSelectFieldModel>;
export type MultiselectField = z.infer<typeof MultiselectFieldModel>;
export type BooleanField = z.infer<typeof BooleanFieldModel>;
export type KVOptionsField = z.infer<typeof KVOptionsFieldModel>;

export type EditorField = z.infer<typeof EditorFieldModel>;
