import { createTheme } from "@mui/material";

export const theme = createTheme({
    palette: {
        mode: 'dark',
        background: {
            default: "#000",
            paper: "#191919"
        }
    },
    typography: {
        fontFamily: "'Montserrat', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    },
    components: {
        MuiListSubheader: {
            styleOverrides: {
                root: {
                    backgroundColor: "unset"
                }
            }
        },
        MuiBackdrop: {
            styleOverrides: {
                root: {
                    backgroundColor: "rgba(0, 0, 0, 0.6)"
                }
            }
        },
        MuiTextField: {
            defaultProps: {
                InputProps: { disableUnderline: true, sx: { borderRadius: "0.2rem" } }
            }
        },
        MuiSelect: {
            defaultProps: {
                disableUnderline: true
            },
            styleOverrides: {
                root: {
                    borderRadius: "0.2rem"
                }
            }
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    backgroundColor: "#000"
                }
            },
            defaultProps: {
                elevation: 0,
            },

        }
    }
});
