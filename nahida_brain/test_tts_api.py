import json
import urllib.request

url = "http://127.0.0.1:9880/tts"

payload = {
    "text": "早上好，我们今天也一起加油吧。",
    "text_lang": "zh",
    "ref_audio_path": "D:/Users/User/Desktop/NahidaProject/GPT-SoVITS/output/slicer_opt/Nahida_Voice_Example.wav_0000697280_0000824640.wav",
    "prompt_text": "不知道干什么的话，要不要我带你去转转呀？",
    "prompt_lang": "zh",
    "top_k": 15,
    "top_p": 0.7,
    "temperature": 0.7,
    "text_split_method": "cut5",
    "batch_size": 1,
    "speed_factor": 1.0,
    "repetition_penalty": 1.35,
    "media_type": "wav",
    "streaming_mode": False
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(request) as response:
    audio = response.read()

with open("nahida_test.wav", "wb") as f:
    f.write(audio)

print("Saved: nahida_test.wav")