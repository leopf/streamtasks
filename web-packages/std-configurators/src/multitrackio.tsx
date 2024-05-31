import { z } from "zod";
import { Box, IconButton, Stack, ThemeProvider, Typography } from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon } from "@mui/icons-material";
import cloneDeep from "clone-deep";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { StaticCLSConfigurator } from "./static";
import { v4 as uuidv4 } from "uuid";
import { MetadataModel, StaticEditor, parseMetadataField, GraphSetter, createCLSConfigurator, EditorField, EditorFieldModel, theme, getConfigModelByFields, Task } from "@streamtasks/core";

const TrackConfigModel = z.object({
    key: z.string(),
    label: z.string().optional(),
    multiLabel: z.string().optional(),
    defaultConfig: z.record(z.any()),
    defaultIO: MetadataModel,
    ioMap: z.record(z.string(), z.string()),
    globalIOMap: z.record(z.string(), z.string()).optional(),
    editorFields: z.array(EditorFieldModel)
});
const TrackConfigsModel = z.array(TrackConfigModel);

type TrackConfig = z.infer<typeof TrackConfigModel>;
type TrackMetadata = { "_key": string } & Record<string, any>;

function TrackList(props: {
    disabledTracks: Set<string>,
    config: TrackConfig,
    data: Record<string, any>,
    onUpdated: () => void,
}) {
    const allFields = useMemo(() => new Set(Object.keys(getConfigModelByFields(props.config.editorFields))), [props.config]);
    const [updateHandle, setUpdate] = useState(0);
    const tracks: TrackMetadata[] = props.data[`${props.config.key}_tracks`] ?? [];
    const setTracks = (tracks: TrackMetadata[]) => {
        props.data[`${props.config.key}_tracks`] = tracks;
        setUpdate(pv => pv + 1);
    };

    const onUpdated = () => {
        props.data[`${props.config.key}_tracks`] = tracks;
        props.onUpdated();
    };

    useEffect(onUpdated, [updateHandle]);

    const onCreate = () => {
        setTracks([...tracks, {
            ...cloneDeep(props.config.defaultConfig),
            "_key": uuidv4()
        }]);
    };

    const onDelete = (key: any) => {
        setTracks(tracks.filter(e => e._key !== key));
    };

    return (
        <Stack spacing={2}>
            <Stack alignItems="center" direction="row">
                <Typography variant="h5" flex={1}>{props.config.multiLabel ?? `${props.config.label ?? props.config.key} tracks`}</Typography>
                <IconButton size="small" onClick={onCreate}>
                    <AddIcon fontSize="inherit" />
                </IconButton>
            </Stack>
            {tracks.map((t, idx) => (
                <Box key={String(t._key) ?? idx}>
                    <Stack direction="row" alignItems="center">
                        <Typography variant="h6" flex={1} gutterBottom>{props.config.label ?? props.config.key} {idx + 1}</Typography>
                        <IconButton size="small" onClick={() => onDelete(t._key)}>
                            <DeleteIcon fontSize="inherit" />
                        </IconButton>
                    </Stack>
                    <StaticEditor disabledFields={props.disabledTracks.has(t._key) ? allFields : new Set()} data={t} fields={props.config.editorFields} onUpdated={onUpdated} />
                </Box>
            ))}
        </Stack>
    );
}

function MultiTrackEditor(props: {
    onUpdated: () => void,
    data: Record<string, any>,
    fields: EditorField[],
    trackConfigs: TrackConfig[],
    disabledTracks: Set<string>,
    disabledFields?: Set<string>
}) {
    return (
        <Stack spacing={3}>
            <StaticEditor data={props.data} fields={props.fields} onUpdated={props.onUpdated} disabledFields={props.disabledFields}/>
            {props.trackConfigs.map(c => <TrackList config={c} data={props.data} disabledTracks={props.disabledTracks} onUpdated={props.onUpdated} />)}
        </Stack>
    );
}

type TrackDescription = {
    config: TrackConfig,
    index: number,
    data: TrackMetadata
};

abstract class MultiTrackConfigurator extends StaticCLSConfigurator {
    protected get trackConfigs() {
        return parseMetadataField(this.taskHost.metadata, "cfg:trackconfigs", TrackConfigsModel, true);
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        const cs = this.getGraph();
        return (
            <ThemeProvider theme={theme}>
                <MultiTrackEditor 
                    disabledTracks={new Set(this.inputs.filter(i => i.topic_id !== undefined).map(i => i.key))} 
                    data={this.config} 
                    fields={this.editorFields} 
                    trackConfigs={this.trackConfigs}
                    disabledFields={cs.getDisabledPaths("config", true)}
                    onUpdated={() => {
                        try {
                            this.beforeUpdate();
                            this.applyConfig();
                            onUpdate();
                        } catch (e) { console.error(e) }
                    }}
                />
            </ThemeProvider>
        )
    }

    protected listTracks() {
        const result: TrackDescription[] = [];
        for (const config of this.trackConfigs) {
            const tracks = this.config[`${config.key}_tracks`] ?? [];
            if (Array.isArray(tracks)) {
                result.push(...tracks.map((track, idx) => ({ config: config, index: idx, data: track })));
            }
        }
        return result;
    }

    protected getTrackConfigByKey(key: string) {
        return this.trackConfigs.find(c => c.key === key);
    }
    protected abstract beforeUpdate(): void;
}

const TrackInputKeysModel = z.array(z.string()); // track._key == input.key
class MultiTrackInputConfigurator extends MultiTrackConfigurator {
    private get trackInputKeys() {
        const result = TrackInputKeysModel.safeParse(this.config._trackInputKeys);
        const keys = result.data ?? [];
        this.config._trackInputKeys = keys;
        return keys;
    }
    private set trackInputKeys(v: string[]) {
        this.config._trackInputKeys = TrackInputKeysModel.parse(v);
    }

    protected beforeUpdate() {
        const tracks = this.listTracks();
        const trackInputKeys = new Set(this.trackInputKeys);

        const trackKeys = new Set(tracks.map(d => d.data._key));

        const deleteInputs = new Set([...trackInputKeys].filter(k => !trackKeys.has(k)));
        this.inputs = this.inputs.filter(i => !deleteInputs.has(i.key));

        for (const track of tracks.filter(t => !trackInputKeys.has(t.data._key))) {
            this.inputs.push({
                key: track.data._key,
                ...track.config.defaultIO
            });
        }

        // set labels
        for (const track of tracks) {
            try {
                const input = this.getInput(track.data._key, false);
                if (!Object.values(track.config.ioMap).includes("label")) {
                    input.label = `${track.config.label ?? track.config.key} ${track.index + 1}`;
                }
            } catch { }
        }

        this.trackInputKeys = tracks.map(t => t.data._key);
    }
    protected getGraph(): GraphSetter<Task> {
        const trackKeyMap = new Map(this.listTracks().map(t => [t.data._key, t]));
        const setter = super.getGraph();
        this.inputs.forEach((input, inputIndex) => {
            const track = trackKeyMap.get(input.key);
            if (!track) return;
            setter.addEdge(`config.${track.config.key}_tracks.${track.index}.in_topic`, `inputs.${inputIndex}.topic_id`);
            for (const [configKey, inputKey] of Object.entries(track.config.ioMap)) {
                setter.addEdge(`config.${track.config.key}_tracks.${track.index}.${configKey}`, `inputs.${inputIndex}.${inputKey}`);
            }
            for (const [configKey, inputKey] of Object.entries(track.config.globalIOMap ?? {})) {
                setter.addEdge(`config.${configKey}`, `inputs.${inputIndex}.${inputKey}`);
            }
            for (const [fieldKey, validator] of Object.entries(getConfigModelByFields(track.config.editorFields))) {
                setter.addValidator(`config.${track.config.key}_tracks.${track.index}.${fieldKey}`, v => validator.safeParse(v).success);
            }
        })
        return setter;
    }
}

const TrackOutputMapModel = z.record(z.string(), z.number().int()); // track._key -> output.topic_id
class MultiTrackOutputConfigurator extends MultiTrackConfigurator {
    private get trackOutputMap() {
        const result = TrackOutputMapModel.safeParse(this.config._trackOutputMap);
        const map = result.data ?? {};
        this.config._trackOutputMap = map;
        return map;
    }
    private set trackOutputMap(v: Record<string, number>) {
        this.config._trackOutputMap = TrackOutputMapModel.parse(v);
    }

    protected beforeUpdate() {
        const tracks = this.listTracks();
        const trackOutputMap = new Map(Object.entries(this.trackOutputMap));

        const trackKeys = new Set(tracks.map(d => d.data._key));

        const deleteOutputsTopicIds = new Set([...trackOutputMap.entries()].filter(([key, _]) => !trackKeys.has(key)).map(([_, topic_id]) => topic_id));
        this.outputs = this.outputs.filter(o => !deleteOutputsTopicIds.has(o.topic_id));
        Array.from(trackOutputMap.keys()).filter(key => !trackKeys.has(key)).forEach(key => trackOutputMap.delete(key)); // delete from map

        for (const track of tracks.filter(t => !trackOutputMap.has(t.data._key))) {
            track.data.out_topic = this.newId();
            trackOutputMap.set(track.data._key, track.data.out_topic);
            this.outputs.push({
                topic_id: track.data.out_topic,
                ...track.config.defaultIO
            });
        }

        for (const track of tracks) {
            try {
                const out_topic = trackOutputMap.get(track.data._key);
                if (out_topic && !Object.values(track.config.ioMap).includes("label")) {
                    const output = this.getOutput(out_topic, false);
                    output.label = `${track.config.label ?? track.config.key} ${track.index + 1}`;
                }
            } catch { }
        }

        this.trackOutputMap = Object.fromEntries(trackOutputMap.entries());
    }
    protected getGraph(): GraphSetter<Task> {
        const trackKeyMap = new Map(this.listTracks().map(t => [t.data._key, t]));
        const output2TrackKeyMap = new Map(Object.entries(this.trackOutputMap).map(([k, v]) => [v, k]));

        const setter = super.getGraph();
        this.outputs.forEach((output, outputIndex) => {
            const trackKey = output2TrackKeyMap.get(output.topic_id);
            if (!trackKey) return;
            const track = trackKeyMap.get(trackKey);
            if (!track) return;
            setter.addEdge(`config.${track.config.key}_tracks.${track.index}.out_topic`, `outputs.${outputIndex}.topic_id`);
            for (const [configKey, inputKey] of Object.entries(track.config.ioMap)) {
                setter.addEdge(`config.${track.config.key}_tracks.${track.index}.${configKey}`, `outputs.${outputIndex}.${inputKey}`);
            }
            for (const [configKey, inputKey] of Object.entries(track.config.globalIOMap ?? {})) {
                setter.addEdge(`config.${configKey}`, `outputs.${outputIndex}.${inputKey}`);
            }
            for (const [fieldKey, validator] of Object.entries(getConfigModelByFields(track.config.editorFields))) {
                setter.addValidator(`config.${track.config.key}_tracks.${track.index}.${fieldKey}`, v => validator.safeParse(v).success);
            }
        })
        return setter;
    }
}

const configurator = createCLSConfigurator((context, task) => {
    const isInput = parseMetadataField(context.taskHost.metadata, "cfg:isinput", z.boolean()) ?? false;
    if (isInput) {
        return new MultiTrackInputConfigurator(context, task);
    }
    else {
        return new MultiTrackOutputConfigurator(context, task);
    }
})
export default configurator;