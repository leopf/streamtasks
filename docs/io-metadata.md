# IO Metadata

Some fields will be ignored when checking if the contents of IOs are compatible. Standard tasks will ignore:
- label
- key
- topic_id

## standards
- `type : "ts" | "id"` Specifies if the messages on this IO have either the field `timestamp` or `id`. Used for synchronization. 
- `content: "image" | "video" | "audio" | any`
- `codec: "raw" | [audio codecs] | [image codecs] | [video codecs] | any` codec used for contents
- `width: int` width of video or image
- `height: int` height of video or image
- `rate: int` Sample rate per second