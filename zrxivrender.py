import os
import json
import nanojekyll

data_dir = 'data/old_documents'
config_yml = '_config.yml'
layout_html = '_layouts/default.html'

config = nanojekyll.yaml_loads(open(config_yml).read())

frontmatter, content = nanojekyll.NanoJekyllTemplate.read_template(layout_html)

docs = {basename : json.load(open(os.path.join(data_dir, basename))) for basename in os.listdir(data_dir) if basename.endswith('.json')}
