import { observer } from "mobx-react-lite";
import { Box, Divider, IconButton, Modal, Stack } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { TopicViewer } from "./TopicViewer";
import { useRootStore } from "../state/root-store";

export const TopicViewerModal = observer(() => {
    const rootStore = useRootStore();

    const close = () => rootStore.uiControl.selectedTopic = undefined;

    return (
        <Modal open={!!rootStore.uiControl.selectedTopic} onClose={close}>
            <Stack position="fixed" top="5%" left="5%" width="90%" height="90%" bgcolor={theme => theme.palette.background.paper} sx={{ backgroundImage: "linear-gradient(rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.16))" }} color={theme => theme.palette.text.primary}>
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