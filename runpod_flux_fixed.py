import os, json, requests, time, base64

api_key = os.environ.get('RUNPOD_API_KEY', '')
endpoint_id = 'pqx9ran607hto0'
sketch_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\canonical_sketch.png'

with open(sketch_path, 'rb') as f:
    sketch_b64 = base64.b64encode(f.read()).decode('utf-8')

prompt = 'manga style, black and white, screen tones, g-pen, 1girl playing guitar on bed, bedroom atmosphere, highly detailed'

workflow = {
    '1': {'inputs': {'ckpt_name': 'flux1-dev-fp8.safetensors'}, 'class_type': 'CheckpointLoaderSimple'},
    '2': {'inputs': {'text': prompt, 'clip': ['1', 1]}, 'class_type': 'CLIPTextEncode'},
    '3': {'inputs': {'pixels': ['4', 0], 'vae': ['1', 2]}, 'class_type': 'VAEEncode'},
    '4': {'inputs': {'image': 'input_sketch.png'}, 'class_type': 'LoadImage'},
    '6': {'inputs': {'seed': 43, 'steps': 20, 'cfg': 1.0, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 0.65, 'model': ['1', 0], 'positive': ['2', 0], 'negative': ['2', 0], 'latent_image': ['3', 0]}, 'class_type': 'KSampler'},
    '7': {'inputs': {'samples': ['6', 0], 'vae': ['1', 2]}, 'class_type': 'VAEDecode'},
    '8': {'inputs': {'filename_prefix': 'CanonManga', 'images': ['7', 0]}, 'class_type': 'SaveImage'}
}

payload = {
    'input': {
        'workflow': workflow,
        'images': [{'name': 'input_sketch.png', 'image': sketch_b64}]
    }
}
url_run = f'https://api.runpod.ai/v2/{endpoint_id}/run'
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}

print('Submitting FIXED FLUX Fallback job...')
resp = requests.post(url_run, headers=headers, json=payload)
if resp.status_code == 200:
    job_id = resp.json()['id']
    print(f'Job ID: {job_id}')
    url_status = f'https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}'
    for i in range(30):
        time.sleep(10)
        s_resp = requests.get(url_status, headers=headers)
        s_data = s_resp.json()
        status = s_data.get('status')
        print(f'Attempt {i}: {status}')
        if status == 'COMPLETED':
            img_data = s_data['output']['images'][0]['data']
            output_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\flux_fallback_manga_result.png'
            with open(output_path, 'wb') as f: f.write(base64.b64decode(img_data))
            print(f'SUCCESS: {output_path} saved.')
            break
        elif status == 'FAILED':
            print('Job FAILED:', s_data)
            break
else:
    print('Submit FAILED:', resp.text)
