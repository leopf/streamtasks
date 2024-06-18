
# streamtasks

![](./screenshot.png)

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

See [connection](connection.md) for more information.