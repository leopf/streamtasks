import { observer, useLocalObservable } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import { useRootStore } from "../state/root-store";
import urlJoin from "url-join";
import { ConnectionManager } from "../components/path-regisrations/ConnectionManager";
import { NamedTopicManager } from "../components/path-regisrations/NamedTopicManager";
import { useEffect } from "react";

export const PathRegistrationPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        id: params.id,
        get regFrontend() {
            return rootStore.pathRegistration.frontendPathRegistrations.find(r => r.id === this.id)
        }
    }));

    useEffect(() => {
        state.id = params.id;
    }, [params.id]);

    if (!state.regFrontend) {
        throw new Error("Not found");
    }

    let innerContent: React.ReactNode = null;
    if (state.regFrontend.frontend.path.startsWith("std:")) {
        if (state.regFrontend.frontend.path === "std:connectionmanager") {
            innerContent = <ConnectionManager pathRegistration={state.regFrontend}/>;
        }
        if (state.regFrontend.frontend.path === "std:namedtopicmanager") {
            innerContent = <NamedTopicManager pathRegistration={state.regFrontend}/>;
        }
    }
    else {
        const url = String(new URL(urlJoin("." + state.regFrontend.path, state.regFrontend.frontend.path), location.href));
        innerContent = <iframe style={{ display: "block", width: "100%", height: "100%", border: "none" }} src={url}></iframe>
    }

    return innerContent;
});