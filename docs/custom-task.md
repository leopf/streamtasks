---
title: Custom tasks
---

# Custom tasks

To create a custom task you should know about [IO Metdata](io-metadata.md).

## functional tasks
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

When calling `run` or `run_sync` you can specify a link, a url or None. When specifying a link it will use the link as its connection. When providing a string, None or no argument it acts like creating a connection with `connect` (see [connection](connection.md)).

### special arguments
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

You can annotate the return type(s) and input types with the `Annotated` type. This allows setting the IO metadata and allowing the mapping of config values to the IO metadata. See [IO Metdata](io-metadata.md) or `examples/fn_task.py` for more information.

## Full Tasks
You can implement anything that can be implemented with tasks by creating a class inheriting `streamtasks.system.task.Task`.

For examples see: streamtasks/system/tasks/**