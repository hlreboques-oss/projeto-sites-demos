import urllib.request, json, re

env = open('/root/evolution-whatsapp-agent/.env').read()
key = re.search(r'AUTHENTICATION_API_KEY=(\S+)', env).group(1)

def call(path, method='GET', body=None):
    url = f'http://127.0.0.1:8085{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={'apikey': key, 'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

insts = call('/instance/fetchInstances')
for i in insts:
    inst = i.get('instance', i)
    print(inst.get('instanceName') or inst.get('name'), inst.get('connectionStatus') or inst.get('status'), inst.get('ownerJid'))

print("---full---")
print(json.dumps(insts, indent=2)[:3000])
