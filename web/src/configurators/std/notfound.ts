import { Task, TaskConfigurator } from "../../types/task";

export default <TaskConfigurator>{
    connect: task => task,
    create: () => {
        throw new Error("Can not create a task with configurator 'std:notfound'!")
    }
};