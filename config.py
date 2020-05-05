import yaml

config = yaml.load(open('test.yml'), Loader=yaml.BaseLoader)

# list of db collections which should exist
collections = [(group.get('db') or group['target language']) \
               for group in config['groups'].values()]

# inverted dictionary with source_channels as keys
source_channels = {}
for translator_group, info in config['groups'].items():
    for source, target in info['source vs target channels']:
        if not source_channels.get(source):
            source_channels[source] = {'target channels':[],
                                       'translator groups':[]}
        source_channels[source]['target channels'].append(target)
        source_channels[source]['translator groups'].append(translator_group)
