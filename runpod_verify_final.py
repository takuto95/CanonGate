import os, json, requests, time, base64

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
    '7': {'inputs': {'image': 'canonical_sketch.png'}, 'class_type': 'LoadImage'},
    '8': {'inputs': {'seed': 42, 'steps': 25, 'cfg': 7.0, 'sampler_name': 'euler_a', 'scheduler': 'karras', 'denoise': 1, 'model': ['1', 0], 'positive': ['6', 0], 'negative': ['3', 0], 'latent_image': ['4', 0]}, 'class_type': 'KSampler'},
    '9': {'inputs': {'samples': ['8', 0], 'vae': ['1', 2]}, 'class_type': 'VAEDecode'},
    '10': {'inputs': {'images': ['9', 0]}, 'class_type': 'SaveImage'}
}

payload = {
    'input': {
        'workflow': workflow,
        'images': [{'name': 'canonical_sketch.png', 'image': sketch_b64}]
    }
}
url_run = f'https://api.runpod.ai/v2/{endpoint_id}/run'
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}

print('Submitting job for verification...')
resp = requests.post(url_run, headers=headers, json=payload)
if resp.status_code == 200:
    job_id = resp.json()['id']
    print(f'Job ID: {job_id}')
    url_status = f'https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}'
    for i in range(60): # 60 attempts = 10 mins (including model load)
        time.sleep(10)
        s_resp = requests.get(url_status, headers=headers)
        s_data = s_resp.json()
        status = s_data.get('status')
        print(f'Attempt {i}: {status}')
        if status == 'COMPLETED':
            img_data = s_data['output']['images'][0]['data']
            output_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\real_gpu_manga_production_v1.png'
            with open(output_path, 'wb') as f: f.write(base64.b64decode(img_data))
            print(f'SUCCESS: {output_path} saved.')
            break
        elif status == 'FAILED':
            print('Job FAILED:', s_data)
            break
else:
    print('Submit FAILED:', resp.text)
