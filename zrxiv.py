import os
import re
import sys
import json
import argparse
import urllib.request
import xml.dom.minidom

def import_arxiv_urls(urls):
    xml_tag_contents = lambda elem, tagName, idx = 0: [textNode.firstChild.nodeValue.strip() for textNode in elem.getElementsByTagName(tagName)]
    
    arxiv_ids = [url.split('arxiv.org/abs/')[-1] for url in urls]
    entries = xml.dom.minidom.parse(urllib.request.urlopen('https://export.arxiv.org/api/query?id_list=' + ','.join(arxiv_ids))).getElementsByTagName('entry')
    
    res = []
    for url, entry in zip(urls, entries):
        arxiv_id = xml_tag_contents(entry, 'id')[0].split('abs/')[1].split('v')[0].replace('/', '_')
        authors = xml_tag_contents(entry, 'name') 
        res.append(dict(
            title = xml_tag_contents(entry, 'title')[0],
            authors = authors,
            url = url,
            abstract = xml_tag_contents(entry, 'summary')[0].replace('\n', ' '),
            id = 'arxiv.' + arxiv_id,
            bibtex_citation_key = 'arxiv.' + arxiv_id,
            bibtex_record_type = 'misc',
            bibtex_author = ' and '.join(authors),
        ))
    return res

def normalize_arxiv_url(url):
    arxiv_id = re.fullmatch(r'\d{4}\.\d+', url)
    if arxiv_id is not None:
        arxiv_id = url
    
    url = url.replace('http://', 'https://') if 'http://' in url else (url if 'https://' in url else f'https://{url}')

    if url.endswith('.pdf'):
        url = url[:-4]
    
    if 'arxiv.org/abs/' in url:
        arxiv_id = url.split('arxiv.org/abs/')[1]

    elif 'arxiv.org/pdf/' in url:
        arxiv_id = url.split('arxiv.org/pdf/')[1]

    elif 'arxiv.org/ftp/arxiv/papers/' in url:
        arxiv_id = url.split('arxiv.org/ftp/arxiv/papers/')[1].split('/')[1]

    if 'v' in arxiv_id:
        arxiv_id = 'v'.join(arxiv_id.split('v')[:-1])
    
    return f'https://arxiv.org/abs/{arxiv_id}'

def parse_urls(text):
    urls = re.findall(r'[a-zA-Z0-9\/\:\.\?=-]+', text)
    docs_arxiv = import_arxiv_urls([normalize_arxiv_url(u) for u in urls if 'arxiv.org' in u])
    return docs_arxiv

def parse_bibtex(text):
    return []

def format_bibtex(bibs, header_keys = ['title', 'bibtex_author', 'booktitle', 'journal', 'year', 'doi'], footer_keys = ['note', 'pdf', 'url'], exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'authors', 'abstract', 'bibtex'], remap_keys = dict(bibtex_author = 'author')):
    bibstrs = []
    for bib in bibs:
        include_keys = set(bib) - set(exclude_keys)
        keys = [k for k in header_keys if k in include_keys] + [k for k in sorted(bib.keys()) if k in include_keys and k not in header_keys and k not in footer_keys] + [k for k in footer_keys if k in include_keys]
        bib_key_values = ',\n'.join('  {k} = {{{v}}}'.format(k = remap_keys.get(k, k), v = bib.get(k, '')) for k in keys)
        bibstrs.append('@{bibtex_record_type}{{{bibtex_citation_key},\n{bib_key_values}\n}}'.format(bib_key_values = bib_key_values, **bib))
    return '\n\n'.join(bibstrs)

def import_docs(bibs, documents_dir, verbose = False, dry = False, exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'bibtex_author']):
    os.makedirs(documents_dir, exist_ok = True)

    for bib in bibs:
        bib_id = bib.get('id') or str(abs(hash(str(bib))))
        p = os.path.join(documents_dir, bib_id + '.json')
        if verbose:
            print('dry = ', dry, 'saving to ' + p, file = sys.stderr)

        with open(p if not dry else os.devnull, 'w') as f:
            j = {k : v for k, v in bib.items() if k not in exclude_keys}
            s = json.dumps(j, indent = 2, ensure_ascii = False)
            if verbose:
                print(s, end = '\n\n', file = sys.stderr)
            print(s, file = f)

if __name__ == '__main__':
    # https://arxiv.org/abs/cond-mat/9911396 https://arxiv.org/abs/1810.08647 http://arxiv.org/abs/1810.08647v1 https://arxiv.org/pdf/1903.05844.pdf https://arxiv.org/pdf/hep-th/9909024.pdf https://arxiv.org/pdf/1805.04246v1.pdf https://arxiv.org/ftp/arxiv/papers/1206/1206.4614.pdf https://arxiv.org/abs/quant-ph/0101012
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--import', dest = 'import_docs', action = 'store_true')
    parser.add_argument('--verbose', action = 'store_true')
    parser.add_argument('--dry', action = 'store_true')
    parser.add_argument('--documents-dir', default = './data/documents/')
    parser.add_argument('--bibtex-path', nargs = '*', default = [])
    parser.add_argument('--urls-path', nargs = '*', default = [])
    parser.add_argument('urls', nargs = argparse.REMAINDER, default = [])
    args = parser.parse_args()

    open_or_urlopen = lambda p: open(p) if not any(map(p.startswith, ['http://', 'https://'])) else urllib.request.urlopen(p)

    bibtex = '\n\n'.join(open_or_urlopen(p).read() for p in args.bibtex_path)
    urls = '\n\n'.join(open(p).read() for p in args.urls_path) + '\n\n' + '\n'.join(args.urls)
    
    bibs = parse_urls(urls) + parse_bibtex(bibtex)

    print(format_bibtex(bibs))

    if args.import_docs:
        import_docs(bibs, documents_dir = args.documents_dir, verbose = args.verbose, dry = args.dry)
