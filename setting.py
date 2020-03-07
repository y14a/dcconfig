import pathlib
import json
import argparse
import jsonschema
import yaml

# Host setting keys
CONFIG_KEY_HOST = 'hosts'
CONFIG_KEY_HOST_USER = 'user'
CONFIG_KEY_HOST_ADDRESSES = 'addresses'
CONFIG_KEY_HOST_PRIVATEKEY = 'key'
CONFIG_KEY_HOST_ROLE = 'role'

# SSL setting keys
CONFIG_KEY_SSL = 'ssl'
CONFIG_KEY_SSL_CN = 'cn'
CONFIG_KEY_SSL_CA = 'ca'
CONFIG_KEY_SSL_CA_ADDRESSES = 'addresses'

# Kubernetes setting keys
CONFIG_KEY_KUBERNETES = 'kubernetes'

# Domain
CONFIG_KEY_DOMAIN = 'domain'

# Default SSL setting values
CONFIG_DEFAULT_SSL_KEY_SIZE = 2048
CONFIG_DEFAULT_SSL_KEY_ALGORITHM = 'rsa'
CONFIG_DEFAULT_SSL_PROFILE = 'datacenter'

# Default host setting values
CONFIG_DEFAULT_HOST_USER = 'operator2020'

class SSLSetting(object):
    def __init__(self, v: dict):
        self._config = v

    def get_ca_config(self) -> dict:
        return {
            'signing': {
                'default': {
                    'expiry': self._config['expiry'],
                },
                'profiles': {
                    CONFIG_DEFAULT_SSL_PROFILE: {
                        'usages': [ 'signing', 'key encipherment', 'server auth', 'client auth' ],
                        'expiry': self._config['expiry'],
                    }
                }
            }
        }

    def get_ca_cn(self) -> str:
        return ''

    def get_csr_common(self) -> dict:
        return {
            'key': { 'algo': CONFIG_DEFAULT_SSL_KEY_ALGORITHM, 'size': CONFIG_DEFAULT_SSL_KEY_SIZE },
            'names': [{
                'C':  self._config['country'],
                'L':  self._config['locality'],
                'O':  self._config['organization'],
                'ST': self._config['state'],
            }]
        }
    
class KubernetesSetting(object):
    def __init__(self, v: dict):
        self._setting = v

    def get_image(self, name: str) -> dict:
        for image in self._setting['images']:
            if image['name'] == name:
                return { 'image': image['image'], 'version': image['version'] }
        raise KeyError(f'Cannot find {name} image setting')

class DomainSetting(object):
    def __init__(self, v: dict):
        self._setting = v
    
    def name(self):
        return self._setting['name']

class Setting(object):
    CONFIG_SCHEMA = pathlib.Path(__file__).parent.joinpath('config.schema.json')
    def __init__(self, args):
        config_path = pathlib.Path(args.filename)
        with open(self.CONFIG_SCHEMA, 'rb') as fin_schema, open(config_path, 'rb') as fin_config:
            if args.type == 'yaml':
                self._config = yaml.load(fin_config, Loader=yaml.BaseLoader)
            else:
                self._config = json.load(fin_config)
            
            schema = json.load(fin_schema)
            jsonschema.validate(self._config, schema)
    
    def get_hosts(self) -> dict:
        group = dict()
        for host in self._config[CONFIG_KEY_HOST]:
            if host['role'] not in group:
                group[host['role']] = list()
            group[host['role']].append(host['name'])
        return group
    
    def get_hostnames_in_group(self, group_name: str) -> list:
        hostnames = list()
        for host in self._config[CONFIG_KEY_HOST]:
            if host['role'] == group_name:
                hostnames.append(host['name'])
        return hostnames
    
    def get_group_names(self) -> list:
        groups = list()
        for host in self._config[CONFIG_KEY_HOST]:
            if host['role'] not in groups:
                groups.append(host['role'])
        return groups
    
    def _get_attribute_of(self, hostname: str, attribute: str, default=None):
        for host in self._config[CONFIG_KEY_HOST]:
            if host['name'] == hostname:
                v = host.get(attribute, default)
                if v is not None:
                    return v
                else:
                    raise KeyError(f'Attribute "{attribute}" is not found in host "{hostname}"')
        raise KeyError(f'Host {hostname} not found')

    def get_user_of(self, hostname: str) -> str:
        return self._get_attribute_of(hostname, CONFIG_KEY_HOST_USER, CONFIG_DEFAULT_HOST_USER)

    def get_role_of(self, hostname: str) -> str:
        return self._get_attribute_of(hostname, CONFIG_KEY_HOST_ROLE)

    def get_addresses_of(self, hostname: str) -> list:
        return self._get_attribute_of(hostname, CONFIG_KEY_HOST_ADDRESSES)

    def get_first_address_of(self, hostname: str) -> str:
        return self.get_addresses_of(hostname)[0]

    def get_ssh_private_key_of(self, hostname: str) -> str:
        return self._get_attribute_of(hostname, CONFIG_KEY_HOST_PRIVATEKEY)

    @property
    def ssl(self):
        return SSLSetting(self._config[CONFIG_KEY_SSL])
    
    @property
    def kubernetes(self):
        return KubernetesSetting(self._config[CONFIG_KEY_KUBERNETES])

    @property
    def domain(self):
        return DomainSetting(self._config[CONFIG_KEY_DOMAIN])
    
    @staticmethod
    def add_argument(parser: argparse.ArgumentParser):
        parser.add_argument('filename', default='settings.json', help='Configuration file path')
        parser.add_argument('-t', '--type', choices=['yaml', 'json'], default='json')
