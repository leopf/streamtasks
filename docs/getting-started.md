# Getting started

## Installation
```bash
git clone https://github.com/leopf/streamtasks.git
cd streamtasks
pip install .[media,web] # see pyproject.toml for more optional packages
```

## Running a server
This example starts everything you need to get started and try out the system.

```bash
DATA_DIR=.data python examples/server.py
```
Then open http://localhost:8080/ to view the web dashboard.

Learn more about the usage by running:
```bash
python examples/server.py --help
```


## Running a peer
A peer must be connected to a network, that has the necessary components. By default it will connect to a locally running server.
See [architecture](architecture.md) and [environment variables](env.md) for more information.

```bash
DATA_DIR=.data python examples/peer.py
```

Learn more about the usage by running:
```bash
python examples/peer.py --help
```
