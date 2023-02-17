import os
import re
import sys
import json
import time
import argparse
import urllib.request
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
                                    val = val.replace(val[caps[0]:caps[1]+1], re.sub("(^|\s)(\S)", capitalize, val[caps[0]+1:caps[1]]).strip())
                        
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

def parse_bibtex(text):
    parser = Parser(text)
    parser.parse()
    bibs = []
    for v in parser.records.values():
        v['bibtex_citation_key'] = v.pop('id')
        v['bibtex_record_type'] = v.pop('type')
        bibs.append(v)
    return bibs

def import_arxiv_urls(urls, batch_size = 50):
    sanitize_whitespaces = lambda s: ' '.join(s.replace('\n', ' ').split()).strip()
    xml_tag_contents = lambda elem, tagName, idx = 0: [textNode.firstChild.nodeValue.strip() for textNode in elem.getElementsByTagName(tagName)]
    
    bibs = []
    for i in range(0, len(urls), batch_size):
        urls_batch = urls[i:i + batch_size]
        id_list = [url.split('arxiv.org/abs/')[-1] for url in urls_batch]
        entries = xml.dom.minidom.parse(urllib.request.urlopen('https://export.arxiv.org/api/query?id_list=' + ','.join(id_list))).getElementsByTagName('entry')

        for url, entry in zip(urls_batch, entries):
            arxiv_id = xml_tag_contents(entry, 'id')[0].split('abs/')[1].split('v')[0].replace('/', '_')
            authors = xml_tag_contents(entry, 'name') 
            # const bibtex = `@misc{${authors[0].split(' ').pop()}${year}_arXiv:${arxiv_id}, title = {${title}}, author = {${authors.join(', ')}}, year = {${year}}, eprint = {${arxiv_id}}, archivePrefix={arXiv}}`; 
            bibs.append(dict(
                title = sanitize_whitespaces(xml_tag_contents(entry, 'title')[0]),
                authors = authors,
                url = url,
                pdf = url.replace('/abs/', '/pdf/'),
                abstract = sanitize_whitespaces(xml_tag_contents(entry, 'summary')[0]),
                id = 'arxiv.' + arxiv_id,
                source = 'arxiv.org',
                bibtex_citation_key = 'arxiv.' + arxiv_id,
                bibtex_record_type = 'misc',
                bibtex_author = ' and '.join(authors),
            ))
    return bibs

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

def format_bibtex(bibs, terse = False, terse_keys = ['title', 'url'], header_keys = ['title', 'bibtex_author', 'booktitle', 'journal', 'year', 'doi'], footer_keys = ['note', 'pdf', 'url'], exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'authors', 'abstract', 'bibtex'], remap_keys = dict(bibtex_author = 'author')):
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

def import_docs(bibs, documents_dir, verbose = False, dry = False, exclude_keys = ['bibtex_record_type', 'bibtex_citation_key', 'bibtex_author']):
    os.makedirs(documents_dir, exist_ok = True)

    for bib in bibs:
        bib['id'] = bib.get('id') or str(abs(hash(str(bib))))
        bib['date'] = bib.get('date') or int(time.time())
        bib['tags'] = bib.get('tags', [])
        p = os.path.join(documents_dir, bib['id'] + '.json')
        if verbose:
            print('dry =', dry, 'saving to ' + p, file = sys.stderr)

        with open(p if not dry else os.devnull, 'w') as f:
            j = {k : v for k, v in bib.items() if k not in exclude_keys}
            s = json.dumps(j, indent = 2, ensure_ascii = False, sort_keys = True)
            if verbose:
                print(s, end = '\n\n', file = sys.stderr)
            print(s, file = f)

def enrich_docs(bibs):
    pass

if __name__ == '__main__':
    # https://arxiv.org/abs/cond-mat/9911396 https://arxiv.org/abs/1810.08647 http://arxiv.org/abs/1810.08647v1 https://arxiv.org/pdf/1903.05844.pdf https://arxiv.org/pdf/hep-th/9909024.pdf https://arxiv.org/pdf/1805.04246v1.pdf https://arxiv.org/ftp/arxiv/papers/1206/1206.4614.pdf https://arxiv.org/abs/quant-ph/0101012
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--import', dest = 'import_docs', action = 'store_true')
    parser.add_argument('--enrich', dest = 'enrich_docs', action = 'store_true')
    parser.add_argument('--tags', nargs = '*', default = [])
    parser.add_argument('--verbose', action = 'store_true')
    parser.add_argument('--terse', action = 'store_true')
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

    if args.verbose:
        print(format_bibtex(bibs, terse = args.terse))
    
    if args.enrich_docs:
        bibs = enrich_docs(bibs)

    if args.import_docs:
        import_docs(bibs, documents_dir = args.documents_dir, verbose = args.verbose, dry = args.dry)
