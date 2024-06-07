podman run --rm -it \
  --userns=keep-id \
  -e MTX_PROTOCOLS=tcp \
  -e MTX_WEBRTCADDITIONALHOSTS=192.168.x.x \
  -p 8554:8554 \
  -p 8889:8889 \
  -p 8888:8888 \
  -p 1935:1935 \
  docker.io/bluenviron/mediamtx
