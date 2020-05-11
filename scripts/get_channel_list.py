import yaml

config = yaml.load(open('../config.yml'), Loader=yaml.BaseLoader)
url = 'https://t.me/%s'

for translator_group, info in config['groups'].items():
    for source, target in info['source vs target channels']:
        print(url%target)
