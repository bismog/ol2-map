#!/usr/bin/env python3
import os
import docker
import subprocess

'''
c_datas = 
{
    "container_x": {
        "layers": {
            "upper_size": 20,
            "lowers_all_size": 60,
            "lowers": {
                "xxxxxxx_1": 20,
                "xxxxxxx_2": 20,
                "xxxxxxx_3": 20
            }
        }
    },
    "container_y": {
        "layers": {
            "upper_size": 20,
            "lowers_all_size": 40,
            "lowers": {
                "xxxxxxx_1": 20,
                "xxxxxxx_4": 20
            }
        }
    }
}
'''

'''
reuse_layers = 
{
    "xxxxxxx_1": {
        "size": 20,
        "reuse": 3,
        "users": [
            "container_x",
            "container_y"
        ]
    },
    "xxxxxxx_2": {
        "size": 20,
        "reuse": 1,
        "users": [
            "container_z"
        ]
    }
}
'''
reuse_layers = {}

def list_containers():
    cns = []
    client = docker.from_env()
    containers = client.containers.list(all=True)
    cns = [[c.name, c.id] for c in containers]
    return cns

# def dirsize(path):
#     total = 0
#     for root, dirs, files in os.walk(path):
#         for f in files:
#             fp = os.path.join(root, f)
#             try:
#                 total += os.path.getsize(fp)
#             except Exception:
#                 continue
#     return total

# def dirsize(path):
#     total = 0
#     for dir in os.scandir(path):
#         total += os.stat(dir).st_size
#     return total

def dirsize(path):
    return int(subprocess.check_output(['du','-s', path]).split()[0].decode('utf-8'))

def to_human(size):
    if size < 1024.0:
        return "%3.1fKB" % size
    elif size < (1024.0 * 1024.0):
        return "%3.1fMB" % (size / 1024.0)
    elif size < (1024.0 * 1024.0 * 1024.0):
        return "%3.1fGB" % (size / (1024.0 * 1024.0))
    else:
        return "%3.1fTB" % (size / (1024.0 * 1024.0 * 1024.0))


def update_reuse_data(cn, layer):
    if layer.endswith("-init"):
        return
    if layer in reuse_layers.keys():
        reuse_layers[layer]['reuse'] += 1
    else:
        reuse_layers[layer] = {}
        reuse_layers[layer]['size'] = dirsize(layer)
        reuse_layers[layer]['reuse'] = 1
        reuse_layers[layer]['users'] = list()
    reuse_layers[layer]['users'].append(cn)

def get_layers_size(cn, layers):
    layers_size = {}
    upper = layers["UpperDir"]
    lowers = layers["LowerDir"].split(":")

    lower_data = {}
    lowers_all_size = 0
    for lower in lowers:
        # if '6800b466a35eaf401fcc826b8b0cf3677442dd' in lower:
        #     import pdb;pdb.set_trace()
        if lower.endswith('/diff:'):
            lower = lower[:len(lower)-len('/diff:')]
        elif lower.endswith('/diff'):
            lower = lower[:len(lower)-len('/diff')]
        update_reuse_data(cn, lower)
        size = dirsize(lower)
        lower_data.update({lower: size})
        lowers_all_size += size
    layers_size.update(dict(upper_size=dirsize(upper), lowers=lower_data, 
                            lowers_all_size=lowers_all_size))
    return layers_size

def container_data(cid):
    client = docker.from_env()
    container = client.containers.get(cid)
    return container

def container_layers(cid):
    data = container_data(cid)
    layers = data.attrs['GraphDriver']['Data']
    return layers
    
def get_all():
    c_datas = {}
    cns = list_containers()
    for cn,ci in cns:
        layers = container_layers(ci)
        layers_size = get_layers_size(cn, layers)
        c_datas[cn] = {"layers": layers_size}
    return c_datas

def record_containers(data):
    cn_max_len = 0
    for cn in data.keys():
        if cn_max_len < len(cn):
            cn_max_len = len(cn) 
    header = f'{"CONTAINER":<{cn_max_len+4}} {"WRITABLE":<10} {"READONLY":<10}\n'
    buffer = header
    for cn,c_data in data.items():
        writable = to_human(c_data["layers"]["upper_size"])
        readonly = to_human(c_data["layers"]["lowers_all_size"])
        main_line = f'{cn:<{cn_max_len+4}} {writable:<10} {readonly:<10} :\n'
        buffer += main_line
        buffer += f'    writable layers size: {to_human(c_data["layers"]["upper_size"])}\n'
        buffer += f'    readonly layers size: {to_human(c_data["layers"]["lowers_all_size"])}\n'

    with open('containers.txt', 'w') as f:
        f.write(buffer)


def record_layers():
    l_max_len = 0
    for layer in reuse_layers.keys():
        if l_max_len < len(layer):
            l_max_len = len(layer)
    header = f'{"LAYER":<{l_max_len+4}} {"SIZE":<10} {"REUSE":<10}\n'
    buffer = header
    for layer,l_data in reuse_layers.items():
        if layer.startswith('/var/lib/docker/overlay2/'):
            layer = layer[len('/var/lib/docker/overlay2/'):]
        size = to_human(l_data["size"])
        reuse = l_data["reuse"]
        main_line = f'{layer:<{l_max_len+4}} {size:<10} {reuse:<10} :\n'
        buffer += main_line
        buffer += f'    users:\n'
        for user in l_data["users"]:
            buffer += f'      {user}\n'

    with open('layers.txt', 'w') as f:
        f.write(buffer)


if __name__ == '__main__':
    data_all = get_all()
    record_containers(data_all)
    record_layers()

    
