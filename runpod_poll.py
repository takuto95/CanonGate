import os, json, requests, time, base64

api_key = os.environ.get('RUNPOD_API_KEY', '')
endpoint_id = 'pqx9ran607hto0'
job_id = 'sync-1ab7c541-23b4-4de8-bcf6-cb996153c980-e2'

url = f'https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}'
headers = {'Authorization': f'Bearer {api_key}'}

print(f'Polling Job {job_id}...')
for _ in range(30):
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        res = resp.json()
        print('Status:', res.get('status'))
        if res.get('status') == 'COMPLETED':
            img_data = res['output']['images'][0]['data']
            output_path = r'C:\Users\takut\.gemini\antigravity\brain\b791680f-5a46-4d8c-aefc-c4b40c50a6e6\real_gpu_manga_result.png'
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(img_data))
            print(f'SUCCESS: {output_path} saved.')
            break
        elif res.get('status') == 'FAILED':
            print('Job FAILED:', res)
            break
    else:
        print('Error:', resp.status_code)
    time.sleep(10)
