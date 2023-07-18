import { Stack, Box } from "@mui/material";
import { AppModal } from "./AppModel";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { TaskStream, streamToString } from "../../lib/task";
import { z } from "zod";

const NumberMessageModel = z.object({
    value: z.number(),
    timestamp: z.coerce.date(),
});

function getMessageFormatter(stream?: TaskStream) {
    if (stream?.content_type == "number" && !stream.encoding && !stream.extra) {
        return (messageJson: string) => {
            const result = NumberMessageModel.safeParse(JSON.parse(messageJson));
            if (!result.success) {
                return messageJson;
            }
            return `[ ${result.data.timestamp.toLocaleString()} ] value: ${result.data.value}`;
        };
    }
    return () => "";
}

export const TopicDataModal = (props: { stream?: TaskStream, onClose: () => void, taskName: string }) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [ messages, setMessages ] = useState<string[]>([]);

    const isOpen = !!props.stream?.topic_id;
    const title = useMemo(() => props.stream ? `${props.taskName} - ${streamToString(props.stream)}` : "", [props.stream, props.taskName]);
    const formatter = useMemo(() => getMessageFormatter(props.stream), [props.stream]);

    useEffect(() => {
        if (!props.stream?.topic_id) return;
        setMessages([]);

        const socket = new WebSocket(`ws://${window.location.host}/topic/${props.stream.topic_id}/subscribe`);

        socket.onmessage = (event) => {
            setMessages(pv => [...pv, formatter(event.data)]);
        };

        return () => {
            socket.close();
        };
    }, [props.stream]);

    useEffect(() => {
        containerRef.current?.scrollTo(0, containerRef.current.scrollHeight);
    }, [messages]);

    return (
        <AppModal open={isOpen} onClose={props.onClose} title={`Messages for "${title}"`}>
            <Box ref={containerRef} sx={{
                fontFamily: "Consolas, monospace",
                overflowY: "auto",
                maxHeight: "100%"
            }}>
                <Stack spacing={0.5} padding={2} boxSizing={"border-box"}>
                    {isOpen && (
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