import { ParsedTaskHost } from "@streamtasks/core";

export function getTaskHostSearchValues(taskHost: ParsedTaskHost) {
    const values = [ ...taskHost.tags, taskHost.label, taskHost.nodeName ];
    if (taskHost.description) {
        values.push(taskHost.description);
    }
    return values;
}