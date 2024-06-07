import { Box, Typography } from "@mui/material";
import { generalStatusColors } from "../lib/status";
import { GeneralStatus } from "../types/status";

export function StatusBadge(props: { status: GeneralStatus, text: string }) {
    return (
        <Box boxSizing="border-box" bgcolor={generalStatusColors[props.status]} borderRadius={1} paddingX={1} paddingY={0.75}>
            <Typography fontWeight="600" lineHeight="0.9rem" fontSize="0.9rem" color="#fff">{props.text}</Typography>
        </Box>
    );
}