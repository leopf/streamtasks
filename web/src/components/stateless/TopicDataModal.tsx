import { Stack, Box } from "@mui/material";
import { AppModal } from "./AppModel";
import React, { useEffect, useRef, useState } from "react";

export const TopicDataModal = (props: { topic_id?: string, onClose: () => void, title: string }) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [ messages, setMessages ] = useState<string[]>([]);

    useEffect(() => {
        if (!props.topic_id) return;
        setMessages([]);

        const socket = new WebSocket(`ws://${window.location.host}/topic/${props.topic_id}/subscribe`);

        socket.onmessage = (event) => {
            const message = JSON.stringify(JSON.parse(event.data), null, 2);
            setMessages(pv => [...pv, message]);
        };

        return () => {
            socket.close();
        };
    }, [props.topic_id, props.topic_id]);

    useEffect(() => {
        containerRef.current?.scrollTo(0, containerRef.current.scrollHeight);
    }, [messages]);

    return (
        <AppModal open={!!props.topic_id} onClose={props.onClose} title={`Messages for "${props.title}"`}>
            <Box ref={containerRef} sx={{
                fontFamily: "Consolas, monospace",
                overflowY: "auto",
                maxHeight: "100%"
            }}>
                <Stack spacing={0.5} padding={2} boxSizing={"border-box"}>
                    {!!props.topic_id && (
                        messages.map((entry, idx) => {
                            return (<Box sx={{
                                whiteSpace: "pre-wrap",
                            }} key={idx}>{entry}</Box>)
                        })
                    )}
                </Stack>
            </Box>
        </AppModal>
    );
}