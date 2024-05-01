import { z } from "zod";
import { Metadata } from "../../types/task";

export const compareIgnoreMetadataKeys = new Set(["key", "topic_id", "label"]);

export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: true): O;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force: false): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>): O | undefined;
export function parseMetadataField<O>(metadata: Metadata, key: string, model: z.ZodType<O>, force?: boolean) {
    const rawData = metadata[key]; 
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

export class GraphSetter {
    clearSetters() {
        throw new Error("Method not implemented.");
    }
    enable(arg0: string) {
        throw new Error("Method not implemented.");
    }
    private validatorsConstraints: Record<string, (v: any) => boolean> = {};
    private valueConstraints: Record<string, any> = {};
    private disabledPaths = new Set<string>();
    private equalities = new Map<string, string[]>();

    private setters = new Map<string, any>();

    public constrainValidator(field: string, validator: (v: any) => boolean) {
        this.validatorsConstraints[field] = validator;
    }
    public constrainValue(field: string, value: any) {
        this.valueConstraints[field] = value;
    }

    public disable(field: string) {
        this.disabledPaths.add(field);
    }

    public addEquals(field1: string, field2: string) {
        this.equalities.set(field1, [...(this.equalities.get(field1) ?? []), field2]);
        this.equalities.set(field2, [...(this.equalities.get(field2) ?? []), field1]);
    }

    public set(field: string, value: any) {
        const fields = this.getEffectedFields(field);
        for (const field of fields) {
            if (!this.setters.has(field)) {
                this.setters.set(field, value);
            }
            else if (this.setters.get(field) !== value) {
                throw new Error("Setter has a value conflict on field " + field);
            }
        }
    }

    public getDisabledFields(path: string, strip: boolean = true) {
        const paths = new Set([
            ...Object.keys(this.valueConstraints),
            ...Object.keys(this.validatorsConstraints),
            ...Object.keys(this.equalities),
        ].filter(p => p.startsWith(path)));
        const result = new Set<string>();
        const substringStart = strip ? path.length : 0; 
        for (const p of paths) {
            if (this.isDisabled(p)) {
                result.add(p.substring(substringStart));
            }
        }
        return result;
    }

    public isDisabled(field: string): boolean {
        const fields = this.getEffectedFields(field);
        for (const field of fields) {
            if (field in this.valueConstraints) {
                return true;
            }
            for (const disabledPath of this.disabledPaths) {
                if (field.startsWith(disabledPath)) {
                    return true;
                }
            }
        }
        return false;
    }

    public validate(): Record<string, any> {
        const result: Record<string, any> = {};
        for (const [setField, setValue] of this.setters.entries()) {
            // check if any setters are disabled
            for (const disabledPath of this.disabledPaths) {
                if (setField.startsWith(disabledPath)) {
                    throw new Error(`Trying to set field "${setField}" which is in the disabled path "${disabledPath}"!`);
                }
            }
            const validatorConstraint = this.validatorsConstraints[setField];
            if (validatorConstraint && !validatorConstraint(setValue)) {
                throw new Error(`Validation for field "${setField}" failed!`);
            }

            const valueConstraint = this.validatorsConstraints[setField];
            if (valueConstraint !== undefined && valueConstraint !== setValue) {
                throw new Error(`Validation for field "${setField}" failed!`);
            }
            result[setField] = setValue;
        }
        return result;
    }

    private getEffectedFields(field: string) {
        const visitedFields = new Set([field]);
        const newFields = new Set([field]);
        while (newFields.size > 0) {
            const visitFields = Array.from(newFields);
            newFields.clear();
            for (const field of visitFields) {
                const fields = this.equalities.get(field) ?? [];
                for (const nfield of fields) {
                    if (!visitedFields.has(nfield)) {
                        newFields.add(nfield);
                    }
                }
            }
        }
        return visitedFields;
    }
}