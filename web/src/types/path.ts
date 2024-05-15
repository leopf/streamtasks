export type PathRegistrationBase = { id: string; path: string; }
export type PathRegistrationFrontend = PathRegistrationBase & { frontend: {
    label: string;
    path: string;
} }

export type PathRegistration = PathRegistrationBase | PathRegistrationFrontend;