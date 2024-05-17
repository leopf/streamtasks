import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";
import { Box, Checkbox, Divider, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";
import { StatusBadge } from "./StatusBadge";
import { Topic } from "../types/topic";

const MessageInfoModel = z.object({
    timestamp: z.coerce.date().transform(a => a.toLocaleString()),
    id: z.string()
}).partial()

const TopicMessageModel = z.object({
    data: z.any()
});

type MessageInfo = z.infer<typeof MessageInfoModel>;
type TopicMessage = z.infer<typeof TopicMessageModel>;
type ParsedTopicMessage = { id: number, message: TopicMessage, info: MessageInfo }
type ColorFormat = { name: string, pixelSize: number }

const colorFormats: ColorFormat[] = [{ name: "rgb24", pixelSize: 3 }];

function TopicBitmapViewer(props: { message: ParsedTopicMessage }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasContextRef = useRef<CanvasRenderingContext2D | null>(null);
    const [colorFormatName, setColorFormatName] = useState("rgb24");
    const [aspectRatio, setAspectRatio] = useState<[number, number]>([16, 9]);
    const [aspectRatioText, setAspectRatioText] = useState("16:9");

    const aspectRatioIsValid = useMemo(() => {
        const nums = aspectRatioText.split(":").map(p => Number(p));
        return nums.length == 2 && !nums.some(n => Number.isNaN(n))
    }, [aspectRatioText]);
    useEffect(() => {
        const nums = aspectRatioText.split(":").map(p => Number(p));
        if (nums.length == 2 && !nums.some(n => Number.isNaN(n))) {
            setAspectRatio(nums as any);
        }
    }, [aspectRatioText]);
    useEffect(() => {
        if (!canvasContextRef.current) return;
        const hexdata = props.message.message.data["data"];
        if (typeof hexdata !== "string") return;
        const colorFormat = colorFormats.find(cf => cf.name === colorFormatName);
        if (!colorFormat) return;

        const pixelCount = Math.floor(hexdata.length / (colorFormat.pixelSize * 2));
        const aspectRatioSize = aspectRatio[0] * aspectRatio[1];
        const arFactor = Math.sqrt(Math.floor(pixelCount / aspectRatioSize));
        const w = arFactor * aspectRatio[0];
        const h = arFactor * aspectRatio[1];

        if ((w * h * colorFormat.pixelSize * 2) !== hexdata.length) return;


        try {
            const ctx = canvasContextRef.current;
            const imageData = ctx.createImageData(w, h, { colorSpace: "srgb" });
            for (let i = 0; i < pixelCount; i++) {
                const hexBase = i * 6;
                const rawBase = i * 4;

                imageData.data[rawBase + 0] = parseInt(hexdata.substring(hexBase, hexBase + 2), 16);
                imageData.data[rawBase + 1] = parseInt(hexdata.substring(hexBase + 2, hexBase + 4), 16);
                imageData.data[rawBase + 2] = parseInt(hexdata.substring(hexBase + 4, hexBase + 6), 16);
                imageData.data[rawBase + 3] = 255;
            }
            createImageBitmap(imageData).then(bm => {
                const scale = Math.min(ctx.canvas.width / w, ctx.canvas.height / h);
                ctx.drawImage(bm, 0, 0, w * scale, h * scale);
            })
        } catch {

        }
    }, [props.message, aspectRatio]);
    useEffect(() => {
        if (!containerRef.current) return;
        const canvas = document.createElement("canvas");
        containerRef.current.appendChild(canvas);
        canvasContextRef.current = canvas.getContext("2d");
        const resizeCanvas = () => {
            canvas.width = containerRef.current?.clientWidth ?? 0;
            canvas.height = containerRef.current?.clientHeight ?? 0;
        };

        const observer = new ResizeObserver(resizeCanvas);
        observer.observe(containerRef.current);
        return () => {
            observer.disconnect();
        };
    }, []);

    return (
        <Box>
            <Stack padding={1} spacing={1} direction="row">
                <TextField size="small" value={aspectRatioText} error={!aspectRatioIsValid} onInput={e => setAspectRatioText((e.target as HTMLInputElement).value)} label="aspect ratio" />
                <FormControl>
                    <InputLabel htmlFor="bm_display_color_format">color format</InputLabel>
                    <Select
                        id="bm_display_color_format"
                        label="color format"
                        value={colorFormatName}
                        size="small"
                        onChange={e => setColorFormatName(e.target.value)}
                    >
                        {colorFormats.map(cf => <MenuItem value={cf.name} key={cf.name}>{cf.name}</MenuItem>)}
                    </Select>
                </FormControl>
            </Stack>
            <Box height="30vh" ref={containerRef} />
        </Box>
    );
}

export function TopicViewer(props: Topic) {
    const [messages, setMessages] = useState<ParsedTopicMessage[]>([]);
    const [open, setOpen] = useState(false);
    const [bitmapDisplayEnabled, setBitmapDisplayEnabled] = useState(false);

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
            `/topic/${props.topicSpaceId}/${props.topicId}` :
            `/topic/${props.topicId}`;

        const ws = new WebSocket("ws://" + location.host + path);
        ws.binaryType = "arraybuffer";
        ws.addEventListener("open", () => setOpen(true))
        ws.addEventListener("message", (e) => {
            try {
                const message = TopicMessageModel.parse(JSON.parse(e.data));
                const pmessageRes = MessageInfoModel.safeParse(message.data);
                const pmessage: ParsedTopicMessage = {
                    id: ++idCounter,
                    message,
                    info: pmessageRes.success ? pmessageRes.data : {}
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

    const lastMessage = useMemo(() => messages.at(-1), [messages]);

    return (
        <Stack height="100%" width="100%" maxHeight="100%">
            <Stack padding={1} spacing={1} direction="row" alignItems="center">
                <FormControlLabel control={<Checkbox onChange={() => setBitmapDisplayEnabled(pv => !pv)} value={bitmapDisplayEnabled} />} label="bitmap display" />
                <Box flex={1} />
                <StatusBadge status={open ? "ok" : "error"} text={open ? "open" : "closed"} />
            </Stack>
            {lastMessage && bitmapDisplayEnabled && (
                <>
                    <Divider />
                    <TopicBitmapViewer message={lastMessage} />
                </>
            )}
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
                    {messages.map(m => (
                        <Box key={m.id} padding={1} fontSize={"0.9rem"}>
                            {Object.keys(m.info).length > 0 && (
                                <Typography variant="body1">
                                    {Object.entries(m.info).map(([k, v]) => `${k}: ${v}`).join(", ")}
                                </Typography>
                            )}
                            <Typography variant="caption">{JSON.stringify(m.message.data)}</Typography>
                        </Box>
                    ))}
                </Box>
            </Box>
        </Stack>
    )
}