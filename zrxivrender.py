import os
import json
import nanojekyll

data_dir = 'data/old_documents'
config_yml = '_config.yml'
layouts_dir = '_layouts/'
codegen_py = 'nanojekyllcodegen.py'
test_html = 'test.html'

config = nanojekyll.NanoJekyllContext.yaml_loads(open(config_yml).read())

#["bibtex.html",  "default.html",  "json.html",  "txt.html",  "xml.html"]

templates_all = {os.path.splitext(layout_html)[0] : nanojekyll.NanoJekyllContext.read_template(os.path.join(layouts_dir, layout_html)) for layout_html in ['default.html'] }#os.listdir(layouts_dir)}

docs = {basename : json.load(open(os.path.join(data_dir, basename))) for basename in os.listdir(data_dir) if basename.endswith('.json')}
    
cls, python_source = nanojekyll.NanoJekyllContext.codegen({k : v[1] for k, v in templates_all.items()}, global_variables = ['site', 'page'])
with open(codegen_py, 'w') as f:
    f.write(python_source)
#cls = __import__(os.path.splitext(codegen_py)[0]).NanoJekyllContext
print(codegen_py)

ctx = dict(site = config)
ctx['site']['data'] = dict(documents = list(docs.items()))
ctx['site']['pages'] = []

content = cls(ctx).render('default')

print(content, file = open(test_html, 'w'))
print(test_html)
