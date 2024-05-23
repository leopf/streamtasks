import re
from streamtasks.env import get_data_sub_dir

def get_model_data_dir(source: str): return get_data_sub_dir("./models/" + re.sub("[^a-z0-9\\-]", "", source))
