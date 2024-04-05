import { TableContainer, Table, TableHead, TableRow, TableCell, TableBody } from "@mui/material";
import { TaskIO } from "../../types/task";
import { TaskIOLabel } from "./TaskIOLabel";
import { useMemo } from "react";

export function TaskIOTable(props: { taskIO: TaskIO }) {
    const taskIOList = useMemo(() => Array.from(Array(Math.max(props.taskIO.inputs.length || 0, props.taskIO.outputs.length || 0)))
        .map((_, idx) => [props.taskIO.inputs.at(idx), props.taskIO.outputs.at(idx)]).map(([i, o]) => [i ? { ...i } : i, o ? { ...o } : o]), [props.taskIO])

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
                            <TableCell align="left">{i && <TaskIOLabel io={i} />}</TableCell>
                            <TableCell align="right">{o && <TaskIOLabel alignRight io={o} />}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
}