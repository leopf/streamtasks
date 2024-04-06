import { observer, useLocalObservable } from "mobx-react-lite";
import { Box, Divider, IconButton, Modal, Stack, Typography } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { z } from "zod";
import { TopicViewer } from "./TopicViewer";
import { useRootStore } from "../../state/root-store";

const TopicMessageModel = z.object({
    data: z.record(z.string(), z.any())
});

type TopicMessage = z.infer<typeof TopicMessageModel>;

export const TopicViewerModal = observer(() => {
    const rootStore = useRootStore();

    const close = () => rootStore.uiControl.selectedTopic = undefined;

    return (
        <Modal open={!!rootStore.uiControl.selectedTopic} onClose={close}>
            <Stack position="fixed" top="5%" left="5%" width="90%" height="90%" bgcolor="#fff">
                <Stack direction="row" alignItems="center" paddingLeft={2}>
                    <Box flex={1} />
                    <IconButton onClick={close}>
                        <CloseIcon />
                    </IconButton>
                </Stack>
                <Divider />
                {rootStore.uiControl.selectedTopic && <TopicViewer {...rootStore.uiControl.selectedTopic}/>}
            </Stack>
        </Modal>
    );
});