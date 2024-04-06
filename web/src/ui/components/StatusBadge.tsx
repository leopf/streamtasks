import { Box, Typography } from "@mui/material";
import { GeneralStatus } from "../../types/status";
import { generalStatusColors } from "../../lib/status";

export function StatusBadge(props: { status: GeneralStatus, text: string }) {
    return (
        <Box bgcolor={generalStatusColors[props.status]} borderRadius={1} paddingX={1} paddingY={0.75}>
            <Typography lineHeight="0.9rem" fontSize="0.9rem" color="#fff">{props.text}</Typography>
        </Box>
    );
}