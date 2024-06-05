import { TaskConfigurator } from "@streamtasks/core";

export default <TaskConfigurator>{
    connect: task => task,
    create: () => {
        throw new Error("Can not create a task with configurator 'std:notfound'!")
    }
};