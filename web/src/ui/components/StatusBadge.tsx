import { Box, Typography } from "@mui/material";
import { GeneralStatus } from "../../types/status";
import { generalStatusColors } from "../../lib/status";

export function StatusBadge(props: { status: GeneralStatus, text: string, round?: boolean }) {
    return (
        <Box border={props.round ? "2px solid #fff" : undefined} boxSizing="border-box" bgcolor={generalStatusColors[props.status]} borderRadius={props.round ? "50%" : 1} paddingX={1} paddingY={0.75}>
            <Typography fontWeight="bold" lineHeight="0.9rem" fontSize="0.9rem" color="#fff">{props.text}</Typography>
        </Box>
    );
}