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
import { parseMetadataField } from "../../lib/conigurator/helpers";

const TrackConfigModel = z.object({
    key: z.string(),
    label: z.string().optional(),
    max: z.number().int(),
    defaultConfig: MetadataModel,
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
    newId: () => number
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
            "_key": String(props.newId())
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
                    {/* TODO: disabled fields */}
                    <StaticEditor disabledFields={props.disabledIds.has(Number(t._key)) ? allFields : new Set()} data={t} fields={props.config.editorFields} onUpdated={props.onUpdated} />
                </Box>
            ))}
        </Stack>
    );
}

function MultiTrackEditor(props: {
    onUpdated: () => void,
    newId: () => number,
    data: Record<string, any>,
    fields: EditorField[],
    trackConfigs: TrackConfig[],
    disabledIds: Set<number>,
}) {
    return (
        <Stack spacing={3}>
            <StaticEditor data={props.data} fields={props.fields} onUpdated={props.onUpdated} />
            {props.trackConfigs.map(c => <TrackList config={c} data={props.data} disabledIds={props.disabledIds} newId={props.newId} onUpdated={props.onUpdated} />)}
        </Stack>
    );
}

abstract class MultiTrackConfigurator extends StaticCLSConfigurator {
    protected get trackConfigs() {
        return parseMetadataField(this.taskHost.metadata, "cfg:trackconfigs", TrackConfigsModel, true);
    }
    protected get trackEntries() {
        const result: TrackMetadata[] = [];
        for (const config of this.trackConfigs) {
            result.push(...(this.getTrackEntries(config.key) ?? []));
        }
        return result;
    }

    public rrenderEditor(onUpdate: () => void): ReactNode {
        return (
            <MultiTrackEditor disabledIds={new Set()} data={this.config} fields={this.editorFields} trackConfigs={this.trackConfigs} newId={this.newId} onUpdated={() => {
                this.applyConfig(true);
                onUpdate();
            }} />
        )
    }

    protected getTrackEntries(key: string) {
        const trackRes = TrackMetadataListModel.safeParse(this.config[`${key}_tracks`]);
        if (trackRes.success) {
            return trackRes.data;
        }
    }
}

class MultiTrackInputConfigurator extends MultiTrackConfigurator {
    
}

const configurator = createCLSConfigurator((context, task) => new MultiTrackInputConfigurator(context, task))
export default configurator;