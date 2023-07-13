import { useEffect, useState } from "react";
import { DeploymentState } from "../state/deployment";
import { state } from "../state";
import { observer } from "mobx-react";
import { useParams, useNavigate } from "react-router-dom";
import React from "react";
import { AppBar, Box, Dialog, Stack } from "@mui/material";
import { TaskTemplateList } from "../components/stateful/TaskTemplateList";
import { NodeEditor } from "../components/stateless/NodeEditor";
import { TitleBar } from "../components/stateful/TitleBar";
import { DeploymentLabelEditor } from "../components/stateless/DeploymentLabelEditor";

export const NewDeploymentPage = observer((props: { }) => {
    const navigate = useNavigate();
    const [ label, setLabel ] = useState<string>("");

    return (
        <Stack direction="column">
            <TitleBar>
                Hello
            </TitleBar>
            <DeploymentLabelEditor open={true} value={label} onChange={v => setLabel(v)} onClose={async () => {
                const newDeployment = await state.createDeployment(label);
                navigate(`/deployment/view/${newDeployment.id}`);
            }}/>
        </Stack>
    );
});