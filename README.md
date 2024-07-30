
# streamtasks

![](docs/screenshot.png)

Read the [Documentation](https://leopf.github.io/streamtasks).

## Demos
- [llama.cpp chatbot](https://www.youtube.com/watch?v=SK1uyyu2noU)
- [playing sound effects](https://www.youtube.com/watch?v=S6cEn3XuzyM)
- [llama.cpp + tts](https://www.youtube.com/watch?v=j6mSyNTFCM4)
- [video layout and video viewer](https://www.youtube.com/watch?v=-XQbR8R6V-o)
- [audio switching](https://www.youtube.com/watch?v=S7Nr7kXrsT8)
- [audio mixing and scaling](https://www.youtube.com/watch?v=C5yIe2No228)
- [publishing a livestream](https://www.youtube.com/watch?v=ZkH5p3I3e1M)

## Overview

Streamtasks aims to simplify software integration for data pipelines.

### How it works
Streamtasks is built on an internal network that distributes messages. The network is host agnostic. It uses the same network to communicate with services running in the same process as it does to communicate with services on a remote machine.

## Getting started

### Installation

#### Simple

##### Windows (with an MSI)

Go to the [latest Release on Github](https://github.com/leopf/streamtasks/releases/latest) and Download the `.msi` file.
Once downloaded, run it.

Or watch the [demo](https://www.youtube.com/watch?v=MD4xsD691AE).

##### Linux (with flatpak)

Go to the [latest Release on Github](https://github.com/leopf/streamtasks/releases/latest) and Download the `.flatpak` file. If you have a GUI to manage flatpak packages installed, you can just double click the file. Otherwise run `flatpak install <the downloaded filename>`.

Or watch the [demo](https://www.youtube.com/watch?v=7zoyVGFaogE).

#### With pip

```bash
pip install streamtasks[media,inference] # see pyproject.toml for more optional packages
```

#### Hardware encoders and decoders
To use hardware encoders and decoders you must have ffmpeg installed on your system.
Verify that you system installation of ffmpeg has the hardware encoders/decoder with:
```bash
# list decoders
ffmpeg -decoders
# list encoders
ffmpeg -encoders
```
Install streamtasks without `av` binaries.
```bash
pip install streamtasks[media,inference] --no-binary av
```
If you have already installed streamtasks (and `av`), you can reinstall `av` with:
```bash
pip install av --no-binary av --ignore-installed
```

See [the pyav documentation](https://pyav.org/docs/develop/overview/installation.html) for more information.

#### llama.cpp with GPU
To install llama.cpp with GPU support you can either install streamtasks with:
```bash 
CMAKE_ARGS="-DLLAMA_CUBLAS=on" FORCE_CMAKE=1 pip install streamtasks[media,inference]
```

or you can reinstall llama-cpp-python with:

```bash 
CMAKE_ARGS="-DLLAMA_CUBLAS=on" FORCE_CMAKE=1 pip install llama-cpp-python --ignore-installed
```
See [the llama-cpp-python documentation](https://github.com/abetlen/llama-cpp-python) for more information.


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