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
        tags: findMetadataFieldString(taskHost, [ "tags", "cfg:tags" ])?.split(",").map(tag => tag.trim()) ?? [],
        nodeName: findMetadataFieldString(taskHost, [ "nodename" ]),
        description: findMetadataFieldString(taskHost, ["description", "cfg:description"]),
        configurator: findMetadataFieldString(taskHost, [ "js:configurator" ]),
    };
}
