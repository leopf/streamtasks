import pyaudio

SAMPLE_FORMAT_2_PA_TYPE: dict[str, int] = {
  "flt": pyaudio.paFloat32,
  "u8": pyaudio.paUInt8,
  "s16": pyaudio.paInt16,
  "s32": pyaudio.paInt32,
}
