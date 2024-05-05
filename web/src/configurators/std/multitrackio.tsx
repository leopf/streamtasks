import { StaticEditor } from "../../StaticEditor";
import { createCLSConfigurator } from "../../lib/conigurator";
import { z } from "zod";
import { EditorField, EditorFieldModel } from "../../StaticEditor/types";
import { Box, IconButton, Stack, Typography } from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon } from "@mui/icons-material";
import cloneDeep from "clone-deep";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { MetadataModel } from "../../model/task";
import { StaticCLSConfigurator } from "./static";
import { GraphSetter, parseMetadataField } from "../../lib/conigurator/helpers";
import { getFieldValidator } from "../../StaticEditor/util";
import { v4 as uuidv4 } from "uuid";

const TrackConfigModel = z.object({
    key: z.string(),
    label: z.string().optional(),
    max: z.number().int(),
    defaultConfig: MetadataModel,
    defaultIO: MetadataModel,
    ioMap: z.record(z.string(), z.string()),
    editorFields: z.array(EditorFieldModel)
});
const TrackConfigsModel = z.array(TrackConfigModel);

const TrackMetadataModel = z.object({ _key: z.string() }).and(MetadataModel)
const TrackMetadataListModel = TrackMetadataModel.array();

type TrackConfig = z.infer<typeof TrackConfigModel>;
type TrackMetadata = z.infer<typeof TrackMetadataModel>;

function TrackList(props: {
    disabledIds: Set<number>,
    config: TrackConfig,
    data: Record<string, any>,
    onUpdated: () => void,
}) {
    const [tracks, setTracks] = useState(() => {
        const res = TrackMetadataListModel.safeParse(props.data[`${props.config.key}_tracks`])
        if (res.success) {
            return res.data;
        }
        else {
            return [];
        }
    });
    const allFields = useMemo(() => new Set(props.config.editorFields.map(f => f.key)), [props.config]);

    useEffect(() => {
        props.data[`${props.config.key}_tracks`] = tracks;
        props.onUpdated();
    }, [tracks]);

    const onCreate = () => {
        setTracks(pv => [...pv, {
            ...cloneDeep(props.config.defaultConfig),
            "_key": uuidv4()
        }]);
    };

    const onDelete = (key: any) => {
        setTracks(pv => pv.filter(e => e._key !== key));
    };

    return (
        <Stack spacing={2}>
            <Stack alignItems="center" direction="row">
                <Typography variant="h5" flex={1}>{props.config.label ?? props.config.key} tracks</Typography>
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
                    <StaticEditor disabledFields={props.disabledIds.has(Number(t._key)) ? allFields : new Set()} data={t} fields={props.config.editorFields} onUpdated={props.onUpdated} />
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
    disabledIds: Set<number>,
}) {
    return (
        <Stack spacing={3}>
            <StaticEditor data={props.data} fields={props.fields} onUpdated={props.onUpdated} />
            {props.trackConfigs.map(c => <TrackList config={c} data={props.data} disabledIds={props.disabledIds} onUpdated={props.onUpdated} />)}
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
        return (
            <MultiTrackEditor disabledIds={new Set()} data={this.config} fields={this.editorFields} trackConfigs={this.trackConfigs} onUpdated={() => {
                this.beforeUpdate();
                this.applyConfig(true);
                onUpdate();
            }} />
        )
    }

    protected listTracks() {
        const result: TrackDescription[] = [];
        for (const config of this.trackConfigs) {
            const tracks = TrackMetadataListModel.safeParse(this.config[`${config.key}_tracks`]).data ?? [];
            result.push(...tracks.map((track, idx) => ({ config: config, index: idx, data: track })));
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

        const trackKeys = new Set(tracks.map(d => d.data.key));

        const deleteInputs = new Set([...trackInputKeys].filter(k => !trackKeys.has(k)));
        this.inputs = this.inputs.filter(i => deleteInputs.has(i.key));

        for (const track of tracks.filter(t => !trackInputKeys.has(t.data._key))) {
            this.inputs.push({
                key: track.data._key,
                ...track.config.defaultIO
            });
        }

        this.trackInputKeys = tracks.map(t => t.data._key);
    }
    protected getGraph(): GraphSetter {
        const trackKeyMap = new Map(this.listTracks().map(t => [t.data._key, t]));
        const setter = super.getGraph();
        this.inputs.forEach((input, inputIndex) => {
            const track = trackKeyMap.get(input.key);
            if (!track) return;

            setter.addEdge(`config.${track.config.key}_tracks.${track.index}.in_topic`, `inputs.${inputIndex}.topic_id`);
            for (const [configKey, inputKey] of Object.entries(track.config.ioMap)) {
                setter.addEdge(`config.${track.config.key}_tracks.${track.index}.${configKey}`, `inputs.${inputIndex}.${inputKey}`);
            }
            for (const field of track.config.editorFields) {
                setter.constrainValidator(`config.${track.config.key}_tracks.${track.index}.${field.key}`, v => getFieldValidator(field).safeParse(v).success);
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

        const trackKeys = new Set(tracks.map(d => d.data.key));

        const deleteOutputsTopicIds = new Set([...trackOutputMap.entries()].filter(([ key, _ ]) => !trackKeys.has(key)).map(([_, topic_id]) => topic_id));
        this.outputs = this.outputs.filter(o => deleteOutputsTopicIds.has(o.topic_id));
        Array.from(trackOutputMap.keys()).filter(key => !trackKeys.has(key)).forEach(key => trackOutputMap.delete(key)); // delete from map

        for (const track of tracks.filter(t => !trackOutputMap.has(t.data._key))) {
            track.data.out_topic = this.newId();
            this.outputs.push({
                topic_id: track.data.out_topic,
                ...track.config.defaultIO
            });
        }

        this.trackOutputMap = Object.fromEntries(trackOutputMap.entries());
    }
    protected getGraph(): GraphSetter {
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
            for (const field of track.config.editorFields) {
                setter.constrainValidator(`config.${track.config.key}_tracks.${track.index}.${field.key}`, v => getFieldValidator(field).safeParse(v).success);
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