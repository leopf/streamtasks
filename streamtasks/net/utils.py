from streamtasks.net import Endpoint
import re

is_address_name_test: re.Pattern = re.compile("^[0-9].*$", re.RegexFlag.I)

def validate_address_name(name: str):
  if ":" in name: raise ValueError("Address name must not contain a ':'!")
  if is_address_name_test.match(name): raise ValueError("Address name must not start with a decimal digit!")

def endpoint_to_str(ep: Endpoint):
  if isinstance(ep[0], str): validate_address_name(ep[0])
  return str(ep[0]) + ":" + str(ep[1])

def str_to_endpoint(data: str) -> Endpoint:
  parts = data.split(":")
  if len(parts) != 2: raise ValueError("Invalid endpoint string, must have exactly one colon.")
  if is_address_name_test.match(parts[0]): address_res = int(parts[0])
  else: address_res = parts[0]
  return (address_res, int(parts[1]))
