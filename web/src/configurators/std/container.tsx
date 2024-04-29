import { StaticEditor } from "../../StaticEditor";
import { getMetadataKeyDiffs } from "../../lib/task";
import { TaskConfigurator, Task, TaskOutput, TaskConfiguratorContext, TaskInput } from "../../types/task";
import { ReactElementRenderer } from "../../lib/conigurator";
import { compareIgnoreMetadataKeys, getCFGFieldEditorFields, createTaskFromContext, elementEmitUpdate, parseMetadataFieldJson } from "./static/utils";
import { z } from "zod";
import { EditorField } from "../../StaticEditor/types";
import { Box, IconButton, Stack, Typography } from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon } from "@mui/icons-material";
import cloneDeep from "clone-deep";
import { useEffect, useMemo, useState } from "react";

type ContainerConfigBase = {
    videos?: Record<string, any>[];
    audios?: Record<string, any>[];
} & Record<string, any>;

function TrackList(props: {
    label: string,
    tracks: Record<string, any>[],
    fields: EditorField[],
    disabledIds: Set<number>,
    onUpdated: () => void,
    onCreate: () => void,
    onDelete: (t: Record<string, any>) => void
}) {
    const allFields = useMemo(() => new Set(props.fields.map(f => f.key)), [props.fields]);

    return (
        <Stack spacing={2}>
            <Stack alignItems="center" direction="row">
                <Typography variant="h5" flex={1}>{props.label} tracks</Typography>
                <IconButton size="small" onClick={props.onCreate}>
                    <AddIcon fontSize="inherit" />
                </IconButton>
            </Stack>
            {props.tracks.map((t, idx) => (
                <Box key={t._key ?? idx}>
                    <Stack direction="row" alignItems="center">
                        <Typography variant="h6" flex={1} gutterBottom>{props.label} {idx + 1}</Typography>
                        <IconButton size="small" onClick={() => props.onDelete(t)}>
                            <DeleteIcon fontSize="inherit" />
                        </IconButton>
                    </Stack>
                    {/* TODO: disabled fields */}
                    <StaticEditor disabledFields={props.disabledIds.has(t.out_topic) ? allFields : new Set()} data={t} fields={props.fields} onUpdated={props.onUpdated} />
                </Box>
            ))}
        </Stack>
    );
}

function ContainerEditor(props: {
    onUpdated: () => void,
    newTopic: () => number,
    data: ContainerConfigBase,
    mainFields: EditorField[],
    videoFields: EditorField[],
    audioFields: EditorField[],
    disabledIds: Set<number>,
    videoDefaultConfig: Record<string, any>,
    audioDefaultConfig: Record<string, any>,
}) {
    const [videos, setVideos] = useState(props.data.videos ?? []);
    const [audios, setAudios] = useState(props.data.audios ?? []);

    useEffect(() => {
        if (props.data.videos !== videos) {
            props.data.videos = videos;
            props.onUpdated();
        }
    }, [videos]);

    useEffect(() => {
        if (props.data.audios !== audios) {
            props.data.audios = audios;
            props.onUpdated();
        }
    }, [audios]);

    return (
        <Stack spacing={3}>
            <StaticEditor data={props.data} fields={props.mainFields} onUpdated={props.onUpdated} />
            <TrackList label="Video" fields={props.videoFields} disabledIds={props.disabledIds} tracks={videos} onUpdated={props.onUpdated}
                onDelete={(v) => setVideos(pv => pv.filter(video => video !== v))}
                onCreate={() => setVideos(pv => [...pv, { out_topic: props.newTopic(), ...cloneDeep(props.videoDefaultConfig) }])} />
            <TrackList label="Audio" fields={props.audioFields} disabledIds={props.disabledIds} tracks={audios} onUpdated={props.onUpdated}
                onDelete={(a) => setAudios(pv => pv.filter(audio => audio !== a))}
                onCreate={() => setAudios(pv => [...pv, { out_topic: props.newTopic(), ...cloneDeep(props.audioDefaultConfig) }])} />
        </Stack>
    );
}

function createContainerOutputs(task: Task, context: TaskConfiguratorContext): TaskOutput[] {
    const videoConfigMap = parseMetadataFieldJson(context, "cfg:videoiomap", z.record(z.string(), z.string()), false) ?? {};
    const videoDefaultIO = parseMetadataFieldJson(context, "cfg:videoio", z.record(z.string(), z.string()), false) ?? {};
    const videos: (Record<string, any> & { out_topic: number })[] = task.config.videos ?? [];

    const audioConfigMap = parseMetadataFieldJson(context, "cfg:audioiomap", z.record(z.string(), z.string()), false) ?? {};
    const audioDefaultIO = parseMetadataFieldJson(context, "cfg:audioio", z.record(z.string(), z.string()), false) ?? {};
    const audios: (Record<string, any> & { out_topic: number })[] = task.config.audios ?? [];

    return [
        ...videos.map((video, idx) => ({
            ...videoDefaultIO,
            label: `video ${idx + 1}`,
            topic_id: video.out_topic,
            ...Object.fromEntries(Object.entries(videoConfigMap).map(([k, v]) => [v, video[k]]))
        })),
        ...audios.map((audio, idx) => ({
            ...audioDefaultIO,
            label: `audio ${idx + 1}`,
            topic_id: audio.out_topic,
            ...Object.fromEntries(Object.entries(audioConfigMap).map(([k, v]) => [v, audio[k]]))
        }))
    ];
}

function createContainerInputs(task: Task, context: TaskConfiguratorContext): TaskInput[] {
    const outputs = createContainerOutputs(task, context);
    return outputs.map(o => ({
        key: String(o.topic_id),
        ...Object.fromEntries(Object.entries(o).filter(([k, v]) => k !== "topic_id"))
    }))
}

const reactRenderer = new ReactElementRenderer();
const configurator: TaskConfigurator = {
    connect: (task: Task, key: string, output: TaskOutput | undefined, context: TaskConfiguratorContext) => {
        const targetInput = task.inputs.find(input => input.key === key);
        if (!targetInput) {
            throw new Error("Input not found!"); // should not happen during normal operation
        }

        if (!output) {
            targetInput.topic_id = undefined;
        }
        else {
            const diffs = getMetadataKeyDiffs(output, targetInput, compareIgnoreMetadataKeys);
            if (diffs.length == 0) {
                targetInput.topic_id = output.topic_id;
            }
            else {
                if (targetInput.topic_id === output.topic_id) {
                    targetInput.topic_id = undefined;
                }
            }
        }

        const inputKeyTopic = Number(targetInput.key);
        const configs = [ ...(task.config.videos ?? []), ...(task.config.audios ?? []) ];
        const targetConfig = configs.find(c => c.out_topic === inputKeyTopic);
        if (targetConfig) {
            targetConfig.in_topic = targetInput.topic_id;
        } 
        return task;
    },
    create: createTaskFromContext,
    renderEditor: (task: Task, element: HTMLElement, context: TaskConfiguratorContext) => {
        const isInput = z.boolean().parse(Boolean(context.taskHost.metadata["cfg:isinput"]));
        const editorProps = {
            mainFields: getCFGFieldEditorFields(context) ?? [],
            videoFields: getCFGFieldEditorFields(context, "cfg:videoeditorfields") ?? [],
            audioFields: getCFGFieldEditorFields(context, "cfg:audioeditorfields") ?? [],
            videoDefaultConfig: parseMetadataFieldJson(context, "cfg:videoconfig", z.record(z.string(), z.any()), false) ?? {},
            audioDefaultConfig: parseMetadataFieldJson(context, "cfg:audioconfig", z.record(z.string(), z.any()), false) ?? {},
        };
        const disabledIds = new Set(task.inputs.filter(i => !!i.topic_id).map(i => Number(i.key)));
        reactRenderer.render(element, <ContainerEditor key={task.id} disabledIds={disabledIds} data={task.config} {...editorProps} newTopic={context.idGenerator} onUpdated={() => {
            if (isInput) {
                task.outputs = createContainerOutputs(task, context);
            }
            else {
                task.inputs = createContainerInputs(task, context);
            }
            elementEmitUpdate(element, task);
        }} />)
    }
};

export default configurator;