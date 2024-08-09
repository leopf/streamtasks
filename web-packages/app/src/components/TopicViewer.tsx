import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";
import { Box, Divider, Stack, Typography } from "@mui/material";
import { StatusBadge } from "./StatusBadge";
import { Topic } from "../types/topic";

const MessageInfoModel = z.object({
    timestamp: z.coerce.date().transform(a => a.toLocaleString()),
    id: z.string()
}).partial()

const TopicDataMessageModel = z.object({
    type: z.literal("data"),
    data: z.any()
})
const TopicControlMessageModel = z.object({
    type: z.literal("control"),
    data: z.object({ paused: z.boolean() })
})

const TopicMessageModel = z.discriminatedUnion("type", [TopicDataMessageModel, TopicControlMessageModel]);

type TopicDataMessage = z.infer<typeof TopicDataMessageModel>;
type TopicControlMessage = z.infer<typeof TopicControlMessageModel>;
type TopicMessage = TopicDataMessage | TopicControlMessage;
type ParsedTopicMessage = { id: number, message: TopicDataMessage | TopicControlMessage }

export function TopicDataMessageDisplay(props: { message: TopicDataMessage }) {
    const info = useMemo(() => MessageInfoModel.safeParse(props.message.data).data, [props.message]);

    return (
        <Box padding={1}>
            {info && (
                <Typography variant="body1">
                    {Object.entries(info).map(([k, v]) => `${k}: ${v}`).join(", ")}
                </Typography>
            )}
            <Typography variant="caption">{JSON.stringify(props.message.data)}</Typography>
        </Box>
    );
}
export function TopicControlMessageDisplay(props: { message: TopicControlMessage }) {
    return (
        <Box padding={1}>
            <Typography variant="body1">paused: {props.message.data.paused ? "yes" : "no"}</Typography>
        </Box>
    );
}

export function TopicMessageDisplay(props: { message: TopicMessage }) {
    if (props.message.type === "data") return <TopicDataMessageDisplay message={props.message} />;
    else if (props.message.type === "control") return <TopicControlMessageDisplay message={props.message} />;
}

export function TopicViewer(props: Topic) {
    const [messages, setMessages] = useState<ParsedTopicMessage[]>([]);
    const [open, setOpen] = useState(false);

    const scrollDataRef = useRef({
        scrollBottom: true,
        ignoreNextEvent: false
    })
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setMessages([]);
        setOpen(false);
        let idCounter = 0;

        const path = props.topicSpaceId ?
            `./topic/${props.topicSpaceId}/${props.topicId}` :
            `./topic/${props.topicId}`;

        const wsUrl = new URL(path, location.href);
        wsUrl.protocol = "ws:";

        const ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer";
        ws.addEventListener("open", () => setOpen(true))
        ws.addEventListener("message", (e) => {
            try {
                const message = TopicMessageModel.parse(JSON.parse(e.data));
                const pmessage: ParsedTopicMessage = {
                    id: ++idCounter,
                    message,
                }
                setMessages(pv => scrollDataRef.current.scrollBottom ? [...pv.slice(pv.length - 200), pmessage] : [...pv, pmessage])
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
            <Stack padding={1} spacing={1} direction="row" alignItems="center">
                <Box flex={1} />
                <StatusBadge status={open ? "ok" : "error"} text={open ? "open" : "closed"} />
            </Stack>
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
                        scrollDataRef.current.scrollBottom = container.scrollTop + 100 > container.scrollHeight - container.clientHeight;
                    }}>
                    {messages.map(m => <TopicMessageDisplay key={m.id} message={m.message} />)}
                </Box>
            </Box>
        </Stack>
    )
}