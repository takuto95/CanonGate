import os, json, requests, time, base64

# Hardcode keys from the retrieved .env to be 100% sure
api_key = os.environ.get('RUNPOD_API_KEY', '')
endpoint_id = 'pqx9ran607hto0'

sketch_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\canonical_sketch.png'

with open(sketch_path, 'rb') as f:
    sketch_b64 = base64.b64encode(f.read()).decode('utf-8')

prompt = 'score_9, score_8_up, score_7_up, rating_explicit, manga_style, g-pen, hatching, detailed_expressive_eyes, petite, head_ratio_5.5, ring_visibility, girl playing guitar on bed, bedroom atmosphere, soft lighting'

workflow = {
    '1': {'inputs': {'ckpt_name': 'ponyDiffusionV6XL_v6Final.safetensors'}, 'class_type': 'CheckpointLoaderSimple'},
    '2': {'inputs': {'text': prompt, 'clip': ['1', 1]}, 'class_type': 'CLIPTextEncode'},
    '3': {'inputs': {'text': 'score_4, score_5, score_6, low quality, bad anatomy, text, watermark, signature', 'clip': ['1', 1]}, 'class_type': 'CLIPTextEncode'},
    '4': {'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}, 'class_type': 'EmptyLatentImage'},
    '5': {'inputs': {'control_net_name': 'controlnet-canny-sdxl-1.0.safetensors'}, 'class_type': 'ControlNetLoader'},
    '6': {'inputs': {'strength': 0.8, 'conditioning': ['2', 0], 'control_net': ['5', 0], 'image': ['7', 0]}, 'class_type': 'ControlNetApply'},
    '7': {'inputs': {'image': sketch_b64}, 'class_type': 'ETN_LoadImageBase64'},
    '8': {'inputs': {'seed': 42, 'steps': 25, 'cfg': 7.0, 'sampler_name': 'euler_a', 'scheduler': 'karras', 'denoise': 1, 'model': ['1', 0], 'positive': ['6', 0], 'negative': ['3', 0], 'latent_image': ['4', 0]}, 'class_type': 'KSampler'},
    '9': {'inputs': {'samples': ['8', 0], 'vae': ['1', 2]}, 'class_type': 'VAEDecode'},
    '10': {'inputs': {'images': ['9', 0]}, 'class_type': 'SaveImage'}
}

payload = {'input': {'workflow': workflow}}
url = f'https://api.runpod.ai/v2/{endpoint_id}/runsync'
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}

print(f'Sending to RunPod {endpoint_id}...')
resp = requests.post(url, headers=headers, json=payload, timeout=300)
if resp.status_code == 200:
    res = resp.json()
    if 'output' in res and 'images' in res['output']:
        img_data = res['output']['images'][0]['data']
        output_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\real_gpu_manga_result.png'
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(img_data))
        print(f'SUCCESS: {output_path} saved.')
    else:
        print('FAILED: No image in output.', res)
else:
    print('FAILED:', resp.status_code, resp.text)
