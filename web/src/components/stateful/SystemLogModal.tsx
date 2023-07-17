import { Stack, Box } from "@mui/material";
import { observer } from "mobx-react";
import { state } from "../../state";
import { AppModal } from "../stateless/AppModel";
import React, { useEffect, useRef, useState } from "react";
import { reaction } from "mobx";

export const SystemLogModal = observer((props: {}) => {
    const containerRef = useRef<HTMLDivElement | null>(null);

    const scrollToEnd = () => containerRef.current?.scrollTo(0, containerRef.current.scrollHeight)
    useEffect(() => reaction(() => state.systemLogs.logs.length, scrollToEnd), [containerRef.current]);
    useEffect(scrollToEnd, [state.systemLogs.open, containerRef]);
    useEffect(() => {
        if (state.systemLogs.open) {
            const hdl = setInterval(() => state.systemLogs.completeLoadLogs(), 1000);
            return () => clearInterval(hdl);
        }
    }, [state.systemLogs.open]);

    return (
        <AppModal open={state.systemLogs.open} onClose={() => state.systemLogs.toggleOpen()} title="System logs">
            <Box ref={(e) => {
                if (e !== containerRef.current) {
                    containerRef.current = e as HTMLDivElement;
                    scrollToEnd();
                }
            }} sx={{
                fontFamily: "Consolas, monospace",
                overflowY: "auto",
                maxHeight: "100%"
            }}>
                <Stack spacing={0.5} padding={2} boxSizing={"border-box"}>
                    {state.systemLogs.open && (
                        state.systemLogs.logs.map((log) => {
                            return (<Box key={log.id}>{`[${log.timestamp.toLocaleString()}] ${log.level}: ${log.message}`}</Box>)
                        })
                    )}
                </Stack>
            </Box>
        </AppModal>
    );
})