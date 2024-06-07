import { TableContainer, Table, TableHead, TableRow, TableCell, TableBody } from "@mui/material";
import { TaskIOLabel } from "./TaskIOLabel";
import { useMemo } from "react";
import { TaskIO, TaskInput, TaskOutput } from "@streamtasks/core";

export function TaskIOTable(props: { taskIO: TaskIO, allowOpen?: boolean, onOpen?: (topic_id: number) => void }) {
    const taskIOList = useMemo(() => Array.from(Array(Math.max(props.taskIO.inputs.length || 0, props.taskIO.outputs.length || 0)))
        .map((_, idx) => [props.taskIO.inputs.at(idx), props.taskIO.outputs.at(idx)]).map(([i, o]) => [i ? { ...i } : i, o ? { ...o } : o]), [props.taskIO])

    const newOnOpenHandler = (io: undefined | TaskInput | TaskOutput) => io ? (() => io.topic_id && props.onOpen?.call(null, io.topic_id)) : undefined;

    return (
        <TableContainer>
            <Table size="small">
                <TableHead>
                    <TableRow>
                        <TableCell align="left">inputs</TableCell>
                        <TableCell align="right">outputs</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {taskIOList.map(([i, o]) => (
                        <TableRow key={String(i?.key) + String(o?.topic_id)}>
                            <TableCell align="left">{i && <TaskIOLabel allowOpen={props.allowOpen && !!i.topic_id} io={i} onOpen={newOnOpenHandler(i)}/>}</TableCell>
                            <TableCell align="right">{o && <TaskIOLabel allowOpen={props.allowOpen && !!o.topic_id} io={o} onOpen={newOnOpenHandler(o)} alignRight />}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
}