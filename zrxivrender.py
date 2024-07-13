import os
import json
import nanojekyll

output_dir = '_site'
data_dir = 'data'
docs_dir = 'data/old_documents'
config_yml = '_config.yml'
layouts_dir = '_layouts'
codegen_py = 'nanojekyllcodegen.py'
# /recent.bib /recent.json /recent.txt /recent.rss
# /all /import /giant

config = nanojekyll.NanoJekyllContext.yaml_loads(open(config_yml).read())

templates_all = {os.path.splitext(layout_html)[0] : nanojekyll.NanoJekyllContext.read_template(os.path.join(layouts_dir, layout_html)) for layout_html in os.listdir(layouts_dir)}

docs = {basename : json.load(open(os.path.join(docs_dir, basename))) for basename in os.listdir(docs_dir) if basename.endswith('.json')}
    
python_source = str(nanojekyll.NanoJekyllContext(templates = {k : v[1] for k, v in templates_all.items()}, global_variables = ['site', 'page']))
cls = nanojekyll.NanoJekyllContext.load_class(python_source)
with open(codegen_py, 'w') as f:
    f.write(python_source)
#cls = __import__(os.path.splitext(codegen_py)[0]).NanoJekyllContext
print(codegen_py)

ctx = dict(site = dict(config, pages = [], data = dict(documents = list(docs.items()))))

os.makedirs(output_dir, exist_ok = True)

print(cls(dict(ctx, page = dict(name = 'all.md', recent_docs = False, path = 'all.md'))).render('default'), file = open(os.path.join(output_dir, 'all.html'), 'w'))
print(cls(dict(ctx, page = dict(name = 'all_bib.md'))).render('bibtex'), file = open(os.path.join(output_dir, 'all.bib'), 'w'))
print(cls(dict(ctx, page = dict(name = 'all_json.md'))).render('json'), file = open(os.path.join(output_dir, 'all.json'), 'w'))
print(cls(dict(ctx, page = dict(name = 'all_txt.md'))).render('txt'), file = open(os.path.join(output_dir, 'all.txt'), 'w'))

print(cls(dict(ctx, page = dict(name = 'recent.md', recent_docs = True, path = 'recent.md'))).render('default'), file = open(os.path.join(output_dir, 'index.html'), 'w'))
print(cls(dict(ctx, page = dict(name = 'recent_bib.md'))).render('bibtex'), file = open(os.path.join(output_dir, 'recent.bib'), 'w'))
print(cls(dict(ctx, page = dict(name = 'recent_json.md'))).render('json'), file = open(os.path.join(output_dir, 'recent.json'), 'w'))
print(cls(dict(ctx, page = dict(name = 'recent_txt.md'))).render('txt'), file = open(os.path.join(output_dir, 'recent.txt'), 'w'))
print(cls(dict(ctx, page = dict(name = 'recent_xml.md', path = 'recent_xml.md'))).render('xml'), file = open(os.path.join(output_dir, 'recent.xml'), 'w'))

print(cls(dict(ctx, page = dict(name = 'import.md', import_docs = True))).render('default'), file = open(os.path.join(output_dir, 'import.html'), 'w'))
for tag_md in os.listdir(os.path.join(data_dir, 'tags')):
    basename = tag_md[:-3]
    os.makedirs(os.path.join(output_dir, basename), exist_ok = True)
    print(cls(dict(ctx, page = dict(name = tag_md, path = os.path.join(data_dir, 'tags', tag_md)))).render('default'), file = open(os.path.join(output_dir, basename, 'index.html'), 'w'))
for tag_md in os.listdir(os.path.join(data_dir, 'bibtex')):
    print(cls(dict(ctx, page = dict(name = tag_md))).render('bibtex'), file = open(os.path.join(output_dir, tag_md[:-3] + '.bib'), 'w'))
for tag_md in os.listdir(os.path.join(data_dir, 'json')):
    print(cls(dict(ctx, page = dict(name = tag_md))).render('json'), file = open(os.path.join(output_dir, tag_md[:-3] + '.json'), 'w'))
for tag_md in os.listdir(os.path.join(data_dir, 'txt')):
    print(cls(dict(ctx, page = dict(name = tag_md))).render('txt'), file = open(os.path.join(output_dir, tag_md[:-3] + '.txt'), 'w'))
for tag_md in os.listdir(os.path.join(data_dir, 'xml')):
    print(cls(dict(ctx, page = dict(name = tag_md, path = os.path.join(data_dir, 'xml', tag_md)))).render('xml'), file = open(os.path.join(output_dir, tag_md[:-3] + '.xml'), 'w'))
