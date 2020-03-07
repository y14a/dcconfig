import pathlib
import json
import argparse
import logging
import sys
import traceback
import string

import yaml

from setting import Setting

# Program name
PROGRAM_NAME = 'genconfig'

# Common names for Kubernetes
MASTER_ROLES = [
    'kube-controller-manager',
    'kube-scheduler',
    'kube-proxy',
    'kube-apiserver',
    'etcd',
]

def get_ssl_csr_json(settings: Setting, **kwargs):
    csr = settings.ssl.get_csr_common()
    if 'hosts' in kwargs:
        csr['hosts'] = kwargs['hosts']
    if 'cn' in kwargs:
        csr['CN'] = kwargs['cn']

    return json.dumps(csr, indent=2)

def generate_ssl_ca_csr(settings: Setting, destdir: pathlib.Path):
    dest = destdir.joinpath('ca')
    dest.mkdir(parents=True, exist_ok=True)

    with open(dest.joinpath('ca.config.json'), 'w') as fout:
        fout.write(json.dumps(settings.ssl.get_ca_config(), indent=2))

    with open(dest.joinpath('ca.csr.json'), 'w') as fout:
        fout.write(get_ssl_csr_json(settings, cn=settings.ssl.get_ca_cn()))

def generate_ssl_kubernetes_master_csr(settings: Setting, destdir: pathlib.Path, hostname: str):
    destdir.mkdir(parents=True, exist_ok=True)
    addresses = settings.get_addresses_of(hostname) + [hostname, ]
    for kube_role_name in MASTER_ROLES:
        if kube_role_name == 'kube-proxy':
            csr = get_ssl_csr_json(
                settings, cn=f'system:{kube_role_name}', hosts=addresses, org=f'system:node-proxier')
        else:
            csr = get_ssl_csr_json(
                settings, cn=f'system:{kube_role_name}', hosts=addresses, org=f'system:{kube_role_name}')
        with open(destdir.joinpath(f'{ kube_role_name }.csr.json'), 'w') as fout:
            fout.write(csr)

def generate_ssl_kubernetes_worker_csr(settings: Setting, destdir: pathlib.Path, hostname: str):
    destdir.mkdir(parents=True, exist_ok=True)
    with open(destdir.joinpath(f'kubelet.csr.json'), 'w') as fout:
        fout.write(get_ssl_csr_json(settings, cn=f'system:nodes:{hostname}', org='system:nodes'))

def generate_ssl_host_csr(settings: Setting, destdir: pathlib.Path):
    for group_name in settings.get_group_names():
        for hostname in settings.get_hostnames_in_group(group_name):
            role_name = settings.get_role_of(hostname)
            if role_name == 'master':
                generate_ssl_kubernetes_master_csr(settings, destdir.joinpath(hostname), hostname)
            elif role_name == 'worker':
                generate_ssl_kubernetes_worker_csr(settings, destdir.joinpath(hostname), hostname)

def generate_ssl_kubernetes_serviceaccount_csr(settings: Setting, destdir: pathlib.Path):
    dest = destdir.joinpath('service-account')
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest.joinpath('service-accounts.csr.json'), 'w') as fout:
        fout.write(get_ssl_csr_json(settings, cn=f'service-accounts'))

def generate_ssl_kubernetes_admin_csr(settings: Setting, destdir: pathlib.Path):
    dest = destdir.joinpath('admin')
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest.joinpath(f'admin.csr.json'), 'w') as fout:
        fout.write(get_ssl_csr_json(settings, cn='admin'))

def generate_ansible_inventory_file(settings: Setting, destdir: pathlib.Path):
    inventory = { 'all': { 'children': dict() } }

    for group_name in settings.get_group_names():
        if group_name not in inventory['all']['children']:
            inventory['all']['children'][group_name] = dict()
            inventory['all']['children'][group_name]['hosts'] = dict()
        
        for hostname in settings.get_hostnames_in_group(group_name):
            inventory['all']['children'][group_name]['hosts'][hostname]= {
                'ansible_host': settings.get_first_address_of(hostname),
                'ansible_user': settings.get_user_of(hostname),
                'ansible_ssh_private_key_file': settings.get_ssh_private_key_of(hostname)
            }

    if not destdir.exists():
        destdir.mkdir(parents=True)

    with open(destdir.joinpath('inventory.yml'), 'w') as inventory_file:
        inventory_file.write(yaml.dump(inventory))

def generate_ansible_vars_file(settings: Setting, destdir: pathlib.Path):
    variables = dict()
    variables['kubernetes'] = dict()
    variables['kubernetes']['etcd'] = settings.kubernetes.get_image('etcd')
    variables['kubernetes']['kube-apiserver'] = settings.kubernetes.get_image('kube-apiserver')
    variables['kubernetes']['kube-controller-manager'] = settings.kubernetes.get_image('kube-controller-manager')
    variables['kubernetes']['kube-scheduler'] = settings.kubernetes.get_image('kube-scheduler')
    variables['kubernetes']['kube-proxy'] = settings.kubernetes.get_image('kube-proxy')
    variables['kubernetes']['kubelet'] = settings.kubernetes.get_image('kubelet')

    variables['domain'] = dict()
    variables['domain']['name'] = settings.domain.name()

    if not destdir.exists():
        destdir.mkdir(parents=True)

    with open(destdir.joinpath('settings.yml'), 'w') as varfile:
        varfile.write(yaml.dump(variables))

def main():
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME)
    parser.add_argument('-o', '--output', default='assets')

    Setting.add_argument(parser)

    args = parser.parse_args()

    destdir = pathlib.Path(args.output)
    try:
        settings = Setting(args)
        
        generate_ssl_ca_csr(settings, destdir)
        generate_ssl_host_csr(settings, destdir)
        generate_ssl_kubernetes_serviceaccount_csr(settings, destdir) 
        generate_ssl_kubernetes_admin_csr(settings, destdir)
        
        generate_ansible_inventory_file(settings, destdir)
        generate_ansible_vars_file(settings, destdir)
    except:
        traceback.print_exc()

if __name__ == "__main__":
    main()