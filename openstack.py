import sys
import string
import argparse
import pathlib
import json
import configparser
import yaml

OPENSTACK_DATABASE_SQL = [
    "CREATE DATABASE keystone;",
    "GRANT ALL PRIVILEGES ON keystone.* TO 'keystone'@'localhost' IDENTIFIED BY '{password}';",
    "GRANT ALL PRIVILEGES ON keystone.* TO 'keystone'@'%' IDENTIFIED BY '{password}';",
]

def generate_openstack_config(destdir, config):
    parser = configparser.ConfigParser()
    parser.add_section('galera')
    parser.set('galera', 'wsrep_on', 'ON')
    parser.set('galera', 'wsrep_cluster_name', config['openstack']['database']['cluster'])
    parser.set('galera', 'wsrep_provider', '/usr/lib64/galera/libgalera_smm.so')
    parser.set('galera', 'wsrep_sst_method', 'rsync')
    parser.set('galera', 'wsrep_cluster_address', 
        ','.join([ config['openstack']['hosts'][h]['address'] for h in config['openstack']['hosts'] ]))

    if not destdir.exists():
        destdir.mkdir(parents=True)

    with open(destdir.joinpath('galera.cnf'), 'w') as fout:
        parser.write(fout)

    with open(destdir.joinpath('openstack.sql'), 'w') as fout:
        for sql in OPENSTACK_DATABASE_SQL:
            fout.write(sql.format(**config['openstack']['database']) + '\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Config YAML file')
    parser.add_argument('-o', '--output', default='assets')

    args = parser.parse_args()

    config = None
    with open(args.config, 'rb') as config_file:
        config = yaml.load(config_file, Loader=yaml.BaseLoader)

    destdir = pathlib.Path(args.output)
    generate_openstack_config(destdir.joinpath('openstack'), config)

if __name__ == '__main__':
    main()