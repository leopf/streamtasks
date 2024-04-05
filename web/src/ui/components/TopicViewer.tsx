import { useEffect, useRef, useState } from "react";
import { Topic } from "../../types/topic";
import { z } from "zod";
import { Box, Divider, Stack, Typography } from "@mui/material";

const TopicMessageModel = z.object({
    data: z.record(z.string(), z.any())
});

type TopicMessage = z.infer<typeof TopicMessageModel>;

export function TopicViewer(props: Topic) {
    const [messages, setMessages] = useState<TopicMessage[]>([]);
    const [open, setOpen] = useState(false);

    const scrollDataRef = useRef({
        scrollBottom: true,
        ignoreNextEvent: false
    })
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setMessages([]);
        setOpen(false);

        const path = props.topicSpaceId ?
            `/topic/${props.topicSpaceId}/${props.topicId}` :
            `/topic/${props.topicId}`;

        const ws = new WebSocket("ws://" + location.host + path);
        ws.binaryType = "arraybuffer";
        ws.addEventListener("open", () => setOpen(true))
        ws.addEventListener("message", (e) => {
            try {
                const message = TopicMessageModel.parse(JSON.parse(e.data))
                setMessages(pv => scrollDataRef.current.scrollBottom ? [...pv.slice(pv.length - 200), message] : [...pv, message])
            } catch (error) {
                console.error(error)
            }
        });
        ws.addEventListener("close", () => setOpen(false));
        return () => {
            ws.close();
        };
    }, [props.topicId, props.topicSpaceId]);

    useEffect(() => {
        if (scrollDataRef.current.scrollBottom) {
            scrollDataRef.current.ignoreNextEvent = true;
            containerRef.current?.scrollTo(containerRef.current?.scrollLeft ?? 0, containerRef.current?.scrollHeight ?? 0);
        }
    }, [messages.length]);

    return (
        <Stack height="100%" width="100%" maxHeight="100%">
            <Box padding={1}>
                <Typography fontSize="0.8rem">status: {open ? "open" : "closed"}</Typography>
            </Box>
            <Divider />
            <Box flex={1} width="100%" position="relative">
                <Box sx={{ overflowY: "auto" }} position="absolute" width="100%" height="100%" ref={containerRef}
                    onScroll={() => {
                        if (scrollDataRef.current.ignoreNextEvent) {
                            scrollDataRef.current.ignoreNextEvent = false;
                            return;
                        }
                        const container = containerRef.current;
                        if (!container) return;
                        scrollDataRef.current.scrollBottom = container.scrollTop + 50 > container.scrollHeight - container.clientHeight;
                    }}>
                    {messages.map(m => (<Box padding={1} fontSize={"0.9rem"}>{JSON.stringify(m.data)}</Box>))}
                </Box>
            </Box>
        </Stack>
    )
}