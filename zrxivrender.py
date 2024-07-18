import os
import json
import glob
import argparse

import nanojekyll

parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', '-o', default = '_site/')
parser.add_argument('--config-yml', default = '_config.yml')
parser.add_argument('--codegen-py', default = 'nanojekyllcodegen.py')
parser.add_argument('--layouts-dir', default = '_layouts/')
parser.add_argument('--data-dir', default = 'data/')
parser.add_argument('--docs-dir', default = 'data/old_documents')
parser.add_argument('--github-url', default = '')
parser.add_argument('--github-owner-name', default = '')
parser.add_argument('--baseurl', default = '')
parser.add_argument('--siteurl', default = '')
args = parser.parse_args()

config = nanojekyll.NanoJekyllContext.yaml_loads(open(args.config_yml).read(), convert_int = True, convert_bool = True)

docs = {basename : json.load(open(os.path.join(args.docs_dir, basename))) for basename in os.listdir(args.docs_dir) if basename.endswith('.json')}

templates_all = {os.path.splitext(layout_html)[0] : nanojekyll.NanoJekyllContext.read_template(os.path.join(args.layouts_dir, layout_html)) for layout_html in os.listdir(args.layouts_dir)}
    
python_source = str(nanojekyll.NanoJekyllContext(templates = {k : v[1] for k, v in templates_all.items()}, global_variables = ['site', 'page']))
cls = nanojekyll.NanoJekyllContext.load_class(python_source)
with open(args.codegen_py, 'w') as f:
    f.write(python_source)
#cls = __import__(os.path.splitext(args.codegen_py)[0]).NanoJekyllContext
print(args.codegen_py)

ctx = dict(site = dict(config, siteurl = args.siteurl, baseurl = args.baseurl, github = dict(url = args.github_url, owner_name = args.github_owner_name), pages = [], data = dict(documents = list(docs.items()))))

os.makedirs(args.output_dir, exist_ok = True)
print(args.output_dir)
for d in config['defaults']:
    #if d['scope']['path'] != 'data/tags/*.md':
    #    continue
    if '*' in d['scope']['path']:
        for path in glob.glob(d['scope']['path']):
            output_path = os.path.join(args.output_dir, d['values']['permalink'].replace(':basename', os.path.splitext(os.path.basename(path))[0]).lstrip('/') + 'index.html' * (d['values']['permalink'][-1] == '/'))
            os.makedirs(os.path.dirname(output_path), exist_ok = True)
            print(cls(dict(ctx, page = dict(d['values'], path = path, name = os.path.basename(path)))).render(d['values']['layout']), file = open(output_path, 'w'))
            print(output_path)
    else:
        output_path = os.path.join(args.output_dir, d['values']['permalink'].lstrip('/'))
        print(cls(dict(ctx, page = dict(d['values'], path = d['scope']['path'], name = os.path.basename(d['scope']['path'])))).render(d['values']['layout']), file = open(output_path, 'w'))
        print(output_path)
