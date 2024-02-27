from setuptools import setup

setup(
    name="streamtasks",
    version="0.1.0",
    packages=[
        "streamtasks",
        "streamtasks.bin",
        "streamtasks.comm",
        "streamtasks.media",
        "streamtasks.client",
        "streamtasks.worker",
        "streamtasks.system",
        "streamtasks.tasks",
        "streamtasks.net.message",
    ],
    author="leopf",
    description="A task orchestrator for Python",
    license="MIT",
    install_requires=[
        "typing_extensions",
        "av",
        "msgpack",
        "pydantic",
        "fastavro",
        "numpy",
        "uvicorn",
        "httpx",
        "fastapi",
        "scipy",
        "lark",
        "tinydb",
    ],
    extras_require={
        "dev": [
          "matplotlib",
          "simpleaudio",
          "opencv-python",
        ]
    }
)