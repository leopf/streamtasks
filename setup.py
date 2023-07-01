from setuptools import setup

setup(
    name='streamtasks',
    version='0.1.0',
    packages=['streamtasks', 'streamtasks.bin', 'streamtasks.comm', 'streamtasks.media', 'streamtasks.client', 
        'streamtasks.worker', 'streamtasks.task', 'streamtasks.tasks', 'streamtasks.message'],
    author='leopf',
    description='A task orchestrator for Python',
    license='MIT',
    requires=['typing_extensions', 'av'],
    entry_points={
        'console_scripts': [
            'streamtasks = streamtasks.bin.__init__:main'
        ]
    }
)



