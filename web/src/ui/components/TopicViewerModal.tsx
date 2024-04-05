import { observer, useLocalObservable } from "mobx-react-lite";
import { useUIControl } from "../../state/ui-control-store";
import { useEffect } from "react";
import { Box, Divider, IconButton, Modal, Stack, Typography } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { z } from "zod";
import { TopicViewer } from "./TopicViewer";

const TopicMessageModel = z.object({
    data: z.record(z.string(), z.any())
});

type TopicMessage = z.infer<typeof TopicMessageModel>;

export const TopicViewerModal = observer(() => {
    const uiControl = useUIControl();

    const close = () => uiControl.selectedTopic = undefined;

    return (
        <Modal open={!!uiControl.selectedTopic} onClose={close}>
            <Stack position="fixed" top="5%" left="5%" width="90%" height="90%" bgcolor="#fff">
                <Stack direction="row" alignItems="center" paddingLeft={2}>
                    <Box flex={1} />
                    <IconButton onClick={close}>
                        <CloseIcon />
                    </IconButton>
                </Stack>
                <Divider />
                {uiControl.selectedTopic && <TopicViewer {...uiControl.selectedTopic}/>}
            </Stack>
        </Modal>
    );
});