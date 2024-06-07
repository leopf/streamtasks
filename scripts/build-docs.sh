#!/bin/bash

export D2_THEME=200

find docs -type f -name "*.d2" | while read -r d2_file; do
  svg_file="${d2_file%.d2}.svg"
  d2 "$d2_file" "$svg_file"
done