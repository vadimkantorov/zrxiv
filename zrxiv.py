import os
import re
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import xml.dom.minidom

###########################################################################################
# TODO: https://github.com/aclements/biblib/tree/master/biblib
# USED: https://github.com/ptigas/bibpy/blob/master/bibpy/bib.py
###########################################################################################

def clear_comments(data):
    """Return the bibtex content without comments"""
    res = re.sub(r"(%.*\n)", '', data)
    res = re.sub(r"(comment [^\n]*\n)", '', res)
    return res

class Parser() :
    """Main class for Bibtex parsing"""

    def tokenize(self) :
        """Returns a token iterator"""        
        for item in self.token_re.finditer(self.data):
            i = item.group(0)
            if self.white.match(i) :
                if self.nl.match(i) :
                    self.line += 1
                continue
            else :
                yield i            

    def __init__(self, data) :
        self.data = data    
        self.token = None
        self.token_type = None
        self._next_token = iter(self.tokenize())
        self.hashtable = {}
        self.mode = None
        self.records = {}        
        self.line = 1

        # compile some regexes
        self.white = re.compile(r"[\n|\s]+")
        self.nl = re.compile(r"[\n]")
        self.token_re = re.compile(r"([^\s\"#%'(){}@,=]+|\n|@|\"|{|}|=|,)")
    
    def parse(self) :
        """Parses self.data and stores the parsed bibtex to self.rec"""
        while True :
            try :
                self.next_token()               
                while self.database() :
                    pass            
            except StopIteration :
                break
    
    def next_token(self):
        """Returns next token"""        
        self.token = next(self._next_token)
        #print self.line, self.token
    
    def database(self) :
        """Database"""
        if self.token == '@' :            
            self.next_token()            
            self.entry()
    
    def entry(self) :  
        """Entry"""     
        if self.token.lower() == 'string' :
            self.mode = 'string'
            self.string()
            self.mode = None
        else :
            self.mode = 'record'            
            self.record()
            self.mode = None

    def string(self) :   
        """String"""   
        if self.token.lower() == "string" :
            self.next_token()
            if self.token == "{" :
                self.next_token()
                self.field()
                if self.token == "}" :
                    pass
                else :                      
                    raise NameError("} missing")
    
    def field(self) :
        """Field"""
        name = self.name()
        if self.token == '=' :
            self.next_token()
            value = self.value()            
            if self.mode == 'string' :                
                self.hashtable[name] = value
            return (name, value)            
    
    def value(self) :
        """Value"""
        value = ""
        val = []

        while True :
            if self.token == '"' :              
                while True:
                    self.next_token()
                    if self.token == '"' :
                        break
                    else :
                        val.append(self.token)            
                if self.token == '"' :          
                    self.next_token()
                else :
                    raise NameError("\" missing")
            elif self.token == '{' :            
                brac_counter = 0
                while True:
                    self.next_token()
                    if self.token == '{' :
                        brac_counter += 1
                    if self.token == '}' :              
                        brac_counter -= 1
                    if brac_counter < 0 :
                        break
                    else :
                        val.append(self.token)            
                if self.token == '}' :
                    self.next_token()
                else :
                    raise NameError("} missing")
            elif self.token != "=" and re.match(r"\w|#|,", self.token) :
                value = self.query_hashtable(self.token)
                val.append(value)
                while True:
                    self.next_token()                    
                    # if token is in hashtable then replace                    
                    value = self.query_hashtable(self.token)
                    if re.match(r"[^\w#]|,|}|{", self.token) : #self.token == '' :
                        break
                    else :
                        val.append(value) 

            elif self.token.isdigit() :
                value = self.token
                self.next_token()
            else :
                if self.token in self.hashtable :
                    value = self.hashtable[ self.token ]
                else :
                    value = self.token          
                self.next_token()

            if re.match(r"}|,",self.token ) :
                break            

        value = ' '.join(val)        
        return value

    def query_hashtable( self, s ) :
        if s in self.hashtable :
            return self.hashtable[ self.token ]
        else :
            return s
    
    def name(self) :
        """Returns parsed Name"""
        name = self.token       
        self.next_token()
        return name

    def key(self) : 
        """Returns parsed Key"""    
        key = self.token
        self.next_token()
        return key

    def record(self) : 
        """Record""" 
        if self.token not in ['comment', 'string', 'preamble'] :          
            record_type = self.token
            self.next_token()            
            if self.token == '{' :
                self.next_token()
                key = self.key()
                self.records[ key ] = {}
                self.records[ key ]['type'] = record_type
                self.records[ key ]['id'] = key
                if self.token == ',' :              
                    while True:
                        self.next_token()
                        field = self.field()
                        if field :
                            k = field[0]
                            val = field[1]

                            if k == 'author' :
                                val = self.parse_authors(val)

                            if k == 'year' :
                                val = {'literal':val}
                                k = 'issued'

                            if k == 'pages' :
                                val = val.replace('--', '-')
                                k = 'page'

                            if k == 'title' :
                                #   Preserve capitalization, as described in http://tex.stackexchange.com/questions/7288/preserving-capitalization-in-bibtex-titles
                                #   This will likely choke on nested curly-brackets, but that doesn't seem like an ordinary practice.
                                def capitalize(s):
                                    return s.group(1) + s.group(2).upper()
                                while val.find('{') > -1:
                                    caps = (val.find('{'), val.find('}'))
                                    val = val.replace(val[caps[0]:caps[1]+1], re.sub(r"(^|\s)(\S)", capitalize, val[caps[0]+1:caps[1]]).strip())
                        
                            self.records[ key ][k] = val
                        if self.token != ',' :                      
                            break               
                    if self.token == '}' :
                        pass
                    else :
                        # assume entity ended
                        if self.token == '@' :
                            pass
                        else :                            
                            raise NameError("@ missing")

    def parse_authors( self, authors ) :
        res = []        
        authors = authors.split('and')
        for author in authors :
            _author = author.split(',')
            family = _author[0].strip().rstrip()
            rec = {'family':family}
            try :
                given = _author[1].strip().rstrip()
                rec['given'] = given
            except IndexError:
                pass
            res.append( rec )
        return res
    
    def json(self) :
        """Returns json formated records"""
        return json.dumps({'items':self.records.values()})


###########################################################################################

def parse_bibtex(text, verbose = False):
    parser = Parser(text)
    parser.parse()
    bibs = []
    for v in parser.records.values():
        v['bibtex_citation_key'] = v.pop('id')
        v['bibtex_record_type'] = v.pop('type')
        bibs.append(v)
    return bibs

def sanitize_whitespaces(s):
    return ' '.join(s.replace('\n', ' ').split()).strip()

def fetch_arxiv_urls(urls, batch_size = 50, arxiv_api_url_format = 'https://export.arxiv.org/api/query?id_list={comma_separated_id_list}', arxiv_url_format = 'https://arxiv.org/abs/{arxiv_id}'):
    xml_tag_contents = lambda elem, tagName, idx = 0: [textNode.firstChild.nodeValue.strip() for textNode in elem.getElementsByTagName(tagName)]
    bibs = []
    for i in range(0, len(urls), batch_size):
        urls_batch = urls[i:i + batch_size]
        id_list = [url.split('arxiv.org/abs/')[-1] for url in urls_batch]
        url = arxiv_api_url_format.format(comma_separated_id_list = ','.join(id_list))
        entries = xml.dom.minidom.parse(urllib.request.urlopen(url)).getElementsByTagName('entry')

        for entry in entries:
            # bibtex = `@misc{${authors[0].split(' ').pop()}${year}_arXiv:${arxiv_id}, title = {${title}}, author = {${authors.join(', ')}}, year = {${year}}, eprint = {${arxiv_id}}, archivePrefix={arXiv}}`; 
            arxiv_id = normalize_arxiv_url(xml_tag_contents(entry, 'id')[0]).split('/abs/')[-1]
            id_bibtex = 'arxiv.' + arxiv_id.replace('/', '_')
            url = arxiv_url_format.format(arxiv_id = arxiv_id)
            pdf = url.replace('/abs/', '/pdf/')
            authors = xml_tag_contents(entry, 'name') 
            bibtex = ''
            bibs.append(dict(
                title = sanitize_whitespaces(xml_tag_contents(entry, 'title')[0]),
                authors = authors,
                url = url,
                pdf = pdf,
                bibtex = bibtex,
                abstract = sanitize_whitespaces(xml_tag_contents(entry, 'summary')[0]),
                id = id_bibtex,
                bibtex_citation_key = id_bibtex,
                bibtex_author = ' and '.join(authors),
                bibtex_record_type = 'misc',
                source = 'arxiv.org',
            ))
    return bibs

def fetch_openreview_urls(urls, batch_size = 50):
    bibs = []
    for i in range(0, len(urls), batch_size):
        urls_batch = urls[i:i + batch_size]
        id_list = [url.split('/forum?id=')[-1] for url in urls_batch]
        entries = json.load(urllib.request.urlopen('https://api.openreview.net/notes?ids=' + ','.join(id_list)))['notes']
        for entry in entries:
            openreview_id = entry['id']
            id_bibtex = 'openreview.' + openreview_id.replace('-', '_')
            url = f'https://openreview.net/forum?id={openreview_id}'
            pdf = url.replace('/forum?', '/pdf?')
            authors = entry['content']['authors']
            bibtex = entry['content']['_bibtex']
            # format_bibtex(entry._bibtex, url, pdf),
            bibs.append(dict(
                title = sanitize_whitespaces(entry['content']['title']),
                authors = authors,
                url = url,
                pdf = pdf,
                bibtex = bibtex,
                abstract = sanitize_whitespaces(entry['content']['abstract']),
                id = id_bibtex,
                bibtex_citation_key = id_bibtex,
                bibtex_author = ' and '.join(authors),
                bibtex_record_type = 'misc',
                source = 'openreview.net',
            ))
    return bibs

def normalize_openreview_url(url):
    try:
        openreview_id = dict(urllib.parse.parse_qsl(urllib.request.urlparse(url).query))['id']
    except:
        breakpoint()
    return f'https://openreview.net/forum?id={openreview_id}'

def normalize_arxiv_url(url):
    if 'arxiv.org' not in url:
        arxiv_id = url
    else:
        arxiv_id = urllib.request.urlparse(url).path
        for delete in ['.pdf', '/abs/', '/pdf/']:
            arxiv_id = arxiv_id.replace(delete, '')
        for extract_basename in ['/ftp/arxiv/papers/']:
            if extract_basename in arxiv_id:
                arxiv_id = os.path.basename(arxiv_id)
    if 'v' in arxiv_id:
        arxiv_id = 'v'.join(arxiv_id.split('v')[:-1])
    return f'https://arxiv.org/abs/{arxiv_id}'

def extract_source(url):
    if not url:
        return None
    if 'arxiv.org' in url or re.fullmatch(r'\d{4}\.\d+', url):
        return 'arxiv.org'
    if 'openreview.net' in url:
        return 'openreview.net'
    return None

def normalize_url(orig_url):
    try:
        url = orig_url
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == 'chrome-extension': # and parsed.netloc == 'noogafoofpebimajpfpamcfhoaifemoa' and parsed.path == '/suspended.html': # https://chromewebstore.google.com/detail/the-marvellous-suspender/noogafoofpebimajpfpamcfhoaifemoa?pli=1
            url = urllib.parse.parse_qs(parsed.fragment).get('uri', [''])[0]
        return url, orig_url
    except:
        return '', orig_url

def parse_urls(text, verbose = False):
    normalized = [(normalized_url, orig_url) for url in re.findall(r'\S+', text) for normalized_url, orig_url in [normalize_url(url)] if normalized_url]
    urls, orig_urls = [normalized_url for normalized_url, orig_url in normalized], [orig_url for normalized_url, orig_url in normalized]
    
    sources = list(map(extract_source, urls))
    bibs_arxiv = fetch_arxiv_urls(list(set(normalize_arxiv_url(u) for u, s in zip(urls, sources) if s == 'arxiv.org')))
    bibs_openreview = fetch_openreview_urls(list(set(normalize_openreview_url(u) for u, s in zip(urls, sources) if s == 'openreview.net')))
    
    if verbose:
        print('# from arxiv extracted documents:', len(bibs_arxiv))
        print('# from openreview extracted documents:', len(bibs_openreview))
        print('# unknown sources:', sources.count(None))
        print('# unknown sources:', [u for u, s in zip(urls, sources) if s is None])
    
    bibs = bibs_arxiv + bibs_openreview

    return bibs

def format_bib(bibs, terse = False, terse_keys = ['title', 'url'], header_keys = ['title', 'bibtex_author', 'booktitle', 'journal', 'year', 'doi'], footer_keys = ['note', 'pdf', 'url'], exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'authors', 'abstract', 'bibtex'], remap_keys = dict(bibtex_author = 'author')):
    bibstrs = []
    for bib in bibs:
        if terse:
            keys = terse_keys
        if not terse:
            include_keys = set(bib) - set(exclude_keys)
            keys = [k for k in header_keys if k in include_keys] + [k for k in sorted(bib.keys()) if k in include_keys and k not in header_keys and k not in footer_keys] + [k for k in footer_keys if k in include_keys]
        bib_key_values = ',\n'.join('  {k} = {{{v}}}'.format(k = remap_keys.get(k, k), v = bib.get(k, '')) for k in keys)
        bibstr = '@{bibtex_record_type}{{{bibtex_citation_key},\n{bib_key_values}\n}}'.format(bib_key_values = bib_key_values, **bib)
        if terse:
            bibstr = ' '.join(bibstr.split())
        bibstrs.append(bibstr)
    return ('\n' if terse else '\n\n').join(bibstrs)

def format_txt(bibs, terse = False, ljust = 50, tab = 4):
    bibstrs = []
    for bib in bibs:
        bibstr = bib['url'].ljust(ljust) + ' ' * tab + bib['title']
        if not terse:
            bibstr += ' | ' + ', '.join(bib.get('authors', []))
        bibstrs.append(bibstr)
    return ('\n' if terse else '\n\n').join(sorted(bibstrs))

def import_docs(bibs, documents_dir, tags = [], verbose = False, dry = False, exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'bibtex_author']):
    os.makedirs(documents_dir, exist_ok = True)

    current_year = time.strftime('%Y')
    for bib in bibs:
        bib['id'] = bib.get('id') or str(abs(hash(str(bib))))
        bib['date'] = bib.get('date') or int(time.time())
        bib['tags'] = bib.get('tags', []) + tags + [current_year]
        p = os.path.join(documents_dir, bib['id'] + '.json')
        if verbose:
            print('dry =', dry, 'saving to ' + p, file = sys.stderr)

        with open(p if not dry else os.devnull, 'w') as f:
            j = {k : v for k, v in bib.items() if k not in exclude_keys}
            s = json.dumps(j, indent = 2, ensure_ascii = False, sort_keys = True)
            if verbose:
                print(s, end = '\n\n', file = sys.stderr)
            print(s, file = f)

def enrich_docs(bibs_to_enrich, verbose = False):
    urls = []
    bibs = []
    for bib in bibs_to_enrich:
        if extract_source(bib.get('url')) is not None:
            urls.append(bib['url'])
        else:
            bibs.append(bib)
    bibs += parse_urls('\n'.join(urls))
    return bibs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-path', '-o')
    parser.add_argument('--documents-dir', default = './data/documents/')
    parser.add_argument('--import', dest = 'import_docs', action = 'store_true')
    parser.add_argument('--enrich', dest = 'enrich_docs', action = 'store_true')
    parser.add_argument('--tags', nargs = '*', default = [])
    parser.add_argument('--terse', action = 'store_true')
    parser.add_argument('--dry', action = 'store_true')
    parser.add_argument('--verbose', action = 'store_true')
    parser.add_argument('--bib-path', nargs = '*', default = [])
    parser.add_argument('--txt-path', nargs = '*', default = [])
    parser.add_argument('--csv-path', nargs = '*', default = [])
    parser.add_argument('--json-path', nargs = '*', default = [])
    parser.add_argument('urls', nargs = argparse.REMAINDER, default = [])
    args = parser.parse_args()

    open_or_urlopen = lambda p: open(p) if not any(map(p.startswith, ['http://', 'https://'])) else urllib.request.urlopen(p)
    
    bibtex = '\n\n'.join(open_or_urlopen(p).read() for p in args.bib_path)
    urls = '\n\n'.join(open(p).read() for p in args.txt_path) + '\n\n' + '\n'.join(args.urls)

    bibs_bibtex = parse_bibtex(bibtex, verbose = args.verbose)
    if args.enrich_docs:
        bibs = enrich_docs(bibs, verbose = args.verbose)
    if args.verbose:
        print('# from bibtex extracted documents:', len(bibs_bibtex))
    
    bibs_txt = parse_urls(urls, verbose = args.verbose)
    if args.verbose:
        print('# from txt extracted documents:', len(bibs_txt))

    bibs = {bib['id'] : bib for bib in bibs_bibtex + bibs_txt}.values()
    if args.verbose:
        print('# total extracted documents:', len(bibs))
    
    output_format = 'bib' if (args.output_path or '').endswith('.bib') else 'txt'
    output_file = sys.stdout if args.output_path == '-' else sys.stdout if args.output_path is None and args.verbose else open(args.output_path, 'w') if args.output_path is not None else open(os.devnull, 'w')

    if output_format == 'bib':
        print(format_bib(bibs, terse = args.terse), file = output_file)
    elif output_format == 'txt':
        print(format_txt(bibs, terse = args.terse), file = output_file)

    if args.import_docs:
        import_docs(bibs, documents_dir = args.documents_dir, verbose = args.verbose, dry = args.dry, tags = args.tags)
        print(args.documents_dir)
