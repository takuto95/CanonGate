import urllib.request, json
with urllib.request.urlopen("http://localhost:50021/speakers") as r:
    data = json.loads(r.read())
for s in data:
    for st in s["styles"]:
        print(s["name"], "/", st["name"], "->", st["id"])
