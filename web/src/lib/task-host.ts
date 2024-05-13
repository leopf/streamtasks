import { TaskHost } from "../types/task";
import { ParsedTaskHost } from "../types/task-host";

export const taskHostLabelFields = ["label", "cfg:label"];
export const taskHostDescriptionFields = ["description", "cfg:description"];

function findMetadataFieldString(taskHost: TaskHost, fields: string[]) {
    return fields.map(field => taskHost.metadata[field]).find(value => typeof value === "string") as string | undefined
}

export function parseTaskHost(taskHost: TaskHost): ParsedTaskHost {
    return {
        id: taskHost.id,
        label: findMetadataFieldString(taskHost, ["label", "cfg:label"]) ?? "-",
        nodeName: findMetadataFieldString(taskHost, [ "nodename" ]) ?? "-",
        tags: findMetadataFieldString(taskHost, [ "tags", "cfg:tags" ])?.split(",").map(tag => tag.trim()) ?? [],
        description: findMetadataFieldString(taskHost, ["description", "cfg:description"]),
        configurator: findMetadataFieldString(taskHost, [ "js:configurator" ]),
    };
}

export function getTaskHostSearchValues(taskHost: ParsedTaskHost) {
    const values = [ ...taskHost.tags, taskHost.label, taskHost.nodeName ];
    if (taskHost.description) {
        values.push(taskHost.description);
    }
    return values;
}