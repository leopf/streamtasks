import { Stack, Box } from "@mui/material";
import { observer } from "mobx-react";
import { state } from "../../state";
import { AppModal } from "../stateless/AppModel";
import React, { useEffect, useRef, useState } from "react";
import { reaction } from "mobx";

export const SystemLogModal = observer((props: { }) => {
    const containerRef = useRef<HTMLDivElement | null>(null);

    const scrollToEnd = () => containerRef.current?.scrollTo(0, containerRef.current.scrollHeight)
    useEffect(() => reaction(() => state.logs.length, scrollToEnd), [containerRef.current]);
    useEffect(scrollToEnd, [state.systemLogOpen, containerRef]);

    return (
        <AppModal open={state.systemLogOpen} onClose={() => state.systemLogOpen = false} title="System logs">
            <Stack spacing={2} padding={2} ref={(e) => {
                if (e !== containerRef.current) {
                    containerRef.current = e as HTMLDivElement;
                    scrollToEnd();
                }
            }} sx={{
                fontFamily: "Consolas",
                overflowY: "auto",
                maxHeight: "100%"
            }}>
                {state.systemLogOpen && (
                    state.logs.map((log, i) => {
                        return (<Box key={i}>{`[${log.timestamp.toLocaleString()}] ${log.level}: ${log.message}`}</Box>)
                    })
                )}
            </Stack>
        </AppModal>
    );
})