import os
import json
import nanojekyll

data_dir = 'data/old_documents'
config_yml = '_config.yml'
layout_html = '_layouts/default.html'
codegen_py = 'nanojekyllcodegen.py'
test_html = 'test.html'

config = nanojekyll.yaml_loads(open(config_yml).read())

templates_all = {os.path.splitext(os.path.basename(layout_html))[0] : nanojekyll.NanoJekyllTemplate.read_template(layout_html)}

docs = {basename : json.load(open(os.path.join(data_dir, basename))) for basename in os.listdir(data_dir) if basename.endswith('.json')}
    
cls, python_source = nanojekyll.NanoJekyllTemplate.codegen({k : v[1] for k, v in templates_all.items()}, global_variables = ['site', 'page'])
with open(codegen_py, 'w') as f:
    f.write(python_source)
#cls = __import__(os.path.splitext(codegen_py)[0]).NanoJekyllContext
print(codegen_py)

ctx = dict(site = config)
ctx['site']['data'] = dict(documents = list(docs.items()))
ctx['site']['pages'] = []

content = cls(ctx).render(os.path.splitext(os.path.basename(layout_html))[0])

print(content, file = open(test_html, 'w'))
