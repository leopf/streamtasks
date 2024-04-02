import { TableContainer, Table, TableHead, TableRow, TableCell, TableBody, Box, IconButton, Stack, Typography } from "@mui/material";
import { ManagedTaskInstance } from "../../lib/task";
import { TaskIOLabel } from "./TaskIOLabel";
import { useEffect, useMemo, useRef, useState } from "react";
import { StoredTaskInstanceModel } from "../../model/task";
import { NodeOverlayTile } from "./NodeOverlayTile";
import { Close as CloseIcon } from "@mui/icons-material";

export function TaskEditorWindow(props: { task: ManagedTaskInstance, onClose: () => void }) {
    const resizingRef = useRef(false);
    const customEditorRef = useRef<HTMLDivElement>(null);
    const [addSize, setAddSize] = useState(0);

    const taskIOList = useMemo(() => Array.from(Array(Math.max(props.task.inputs?.length || 0, props.task.outputs?.length || 0)))
        .map((_, idx) => [props.task.inputs?.at(idx), props.task.outputs?.at(idx)]), [props.task])

    useEffect(() => {
        if (!props.task.hasEditor || !customEditorRef.current) return;

        const taskUpdateHandler = (e: Event) => {
            const newInstance = StoredTaskInstanceModel.parse((e as CustomEvent).detail);
            props.task.updateData(newInstance);
            if (customEditorRef.current) props.task.renderEditor(customEditorRef.current)
        };

        customEditorRef.current.addEventListener("task-instance-updated", taskUpdateHandler);
        props.task.renderEditor(customEditorRef.current);

        return () => {
            customEditorRef.current?.removeEventListener("task-instance-updated", taskUpdateHandler)
        }
    }, [props.task, customEditorRef.current]);

    useEffect(() => {
        const mouseUpHandler = () => resizingRef.current = false; 
        const mouseMoveHandler = (e: MouseEvent) => {
            if (!resizingRef.current) return;
            setAddSize(pv => Math.min(0, pv + e.movementY));
        };
        
        window.addEventListener("mouseup", mouseUpHandler);
        window.addEventListener("mousemove", mouseMoveHandler);

        return () => {
            window.removeEventListener("mouseup", mouseUpHandler);
            window.removeEventListener("mousemove", mouseMoveHandler);
        };
    }, []);

    return (
        <Box position="absolute" top="1rem" right="1rem" width="30%" height={`calc(100% - 2rem + ${addSize}px)`}>
            <NodeOverlayTile header={(
                <Stack direction="row" alignItems="center">
                    <Typography fontWeight="bold" fontSize="0.85rem">{props.task.label}</Typography>
                    <Box flex={1} />
                    <IconButton aria-label="close" size="small" onClick={() => props.onClose()}>
                        <CloseIcon fontSize="inherit" />
                    </IconButton>
                </Stack>
            )}>
                <>
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
                                    <TableRow>
                                        <TableCell align="left">{i && <TaskIOLabel io={i} />}</TableCell>
                                        <TableCell align="right">{o && <TaskIOLabel alignRight io={o} />}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    <h1>Test</h1>
                    {props.task.hasEditor && <Box padding={1} ref={customEditorRef} />}
                </>
            </NodeOverlayTile>
            <Box position="absolute" bottom={0} left={0} width={"100%"} height="4px" sx={{ cursor: "ns-resize", userSelect: "none" }} onMouseDown={() => resizingRef.current = true}/>
        </Box>
    )
}