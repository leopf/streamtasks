
# streamtasks

![](docs/screenshot.png)

Read the [Documentation](docs/overview.md).

## Overview

Streamtasks aims to simplify software integration for data pipelines.

### How it works
Streamtasks is built on an internal network that distributes messages. The network is host agnostic. It uses the same network to communicate with services running in the same process as it does to communicate with services on a remote machine.


## Getting started

### Installation
```bash
git clone https://github.com/leopf/streamtasks.git
cd streamtasks
pip install .[media] # see pyproject.toml for more optional packages
```

### Running an instance
You can run an instance of the streamtasks system with `streamtasks -C` or `python -m streamtasks -C`.

The flag `-C` indicates that the core components should be started as well.

Use `streamtasks --help` for more options.

### Connecting two instances
When connecting two instances you need to have one main instance running the core components (using `-C`).

To create a connection endpoint (server), you can use the Connection Manager in the UI or you can specify a url to host a server on as a command line flag.

For example:
```bash
streamtasks -C --serve tcp://127.0.0.1:9002
```

You may specify multiple serve urls.

To connect the second system to the main system, you need to start your second system **without** the core components, specifying a connect url.

For example:
```bash
streamtasks --connect tcp://127.0.0.1:9002
```

See [connection](docs/connection.md) for more information.
## custom tasks

To create a custom task you should know about [IO Metdata](docs/io-metadata.md).

### functional tasks
module: `streamtasks.system.fntask`

This is the simplest way of creating custom tasks.

This can NOT do everything that can be done with tasks.

example:
```python
from streamtasks.system.fntask import fn_task

@fn_task()
def adder(a: int, b: int) -> int: return a + b

if __name__ == "__main__": adder.run_sync()
```

When calling `run` or `run_sync` you can specify a link, a url or None. When specifying a link it will use the link as its connection. When providing a string, None or no argument it acts like creating a connection with `connect` (see [connection](docs/connection.md)).

#### special arguments
`timestamp: int` the timestamp of the newest input parameter

`config: Any` The config must be a type that can be initialized by calling its type (to create the default config). It holds the configuration the task is started with. 

`state: Any` The state must be a type that can be initialized by calling its type. You can use the state to hold data that is task specific and is required accross calls. 

Full example:

```python
from streamtasks.system.fntask import fn_task

from dataclasses import dataclass

@dataclass
class State:
    count: int = 0

@dataclass
class Config:
    step: int = 1

@fn_task()
def demo2(a: int, state: State, config: Config) -> int:
    state.count += config.step
    return a + state.count 

if __name__ == "__main__": demo2.run_sync()
```

You can also specify arguments for the `fn_task` decorator:

`label` - specify a label for the task

`thread_safe` - if the function is thread safe. Used to run synchronous functions in seperate threads.

You can annotate the return type(s) and input types with the `Annotated` type. This allows setting the IO metadata and allowing the mapping of config values to the IO metadata. See [IO Metdata](docs/io-metadata.md) or `examples/fn_task.py` for more information.

### Full Tasks
You can implement anything that can be implemented with tasks by creating a class inheriting `streamtasks.system.task.Task`.

For examples see: streamtasks/system/tasks/**