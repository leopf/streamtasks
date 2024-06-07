# IO Metadata
When configuring Task through the frontend, each input and output has data associated with it. This data describes the data type sent or received on the topic.

The IO metadata can also be used to automatically configure tasks by transfering the metadata into the tasks config when connecting an input. This also works in reverse, by transferring config data to the IO data.

How the IO metadata is handled is dependent on the configurator used for a task. Since configurators are customizable, the bahavior is not strict. As long as the configurator sets the topic_id of its input, it will be connected.

There are some standards.

## Standards

When comparing IO metadata for compatibility the follwing fields are generally ignored:
- label
- key
- topic_id

### field names / values
- `type : "ts" | "id"` Specifies if the messages on this IO have either the field `timestamp` or `id`. Used for synchronization. 
- `content: "video" | "audio" | "number" | "text" | any`
- `codec: "raw" | [audio codecs] | [video codecs] | any` codec used for contents
- `width: int` width of video or image
- `height: int` height of video or image
- `rate: int` sample/frame/message rate per second
- `sample_format: str` the sample format for audio data
- `channels: int` the amount of channels for audio data
- `pixel_format: str` the pixel format for video data

## Mapping of IO Data
When using the standard configurator or the multitrack configurator, config fields can be mapped to IO fields. This is done using an `input_config_map` or an `output_config_map`. 

Inputs have unique keys that are used for mapping, which results in the following 
type for a 

`input_config_map: { [input_key]: { [config_field]: [input_field] } }`

Since outputs don't have keys, they are selected by index. This is done by creating an array entry for each output, or setting the entry to None. Each entry in the `output_config_map` should look like this:

`output_config_map_entry: { [config_field]: [input_field] } | None`

## Functional Tasks
In functional tasks you can specify the IO metadata and IO map by using the `Annotated` type from `typing`.

Type template: `Annotated[type, default_io, io_map]`.

The `type` is the actual python type like `int`.

`default_io` is the default IO data for the input or output as a dict of key value pairs.

`io_map` is the same thing as `output_config_map_entry`, a dict mapping config fields to input/output fields.

See examples/fn_task.py for more information.