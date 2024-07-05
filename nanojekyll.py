import os, sys, re, html, json, datetime
import inspect

def yaml_loads(content, convert_bool = True, convert_int = True, convert_dict = True): # from https://gist.github.com/vadimkantorov/b26eda3645edb13feaa62b874a3e7f6f
    def procval(val):
        read_until = lambda tail, chars: ([(tail[:i], tail[i+1:]) for i, c in enumerate(tail) if c in chars] or [(tail, '')])[0]

        val = val.strip()
        is_quoted_string = len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'"))
        if is_quoted_string:
            return val[1:-1]
        else:
            val = val.split('#', maxsplit = 1)[0].strip()
            is_int = val.isdigit()
            is_bool = val.lower() in ['true', 'false']
            is_dict = len(val) >= 2 and (val[0] == '{' and val[-1] == '}')
            if is_int and convert_int:
                return int(val) if convert_int else val
            elif is_bool and convert_bool:
                return dict(true = True, false = False)[val.lower()] if convert_int else val
            elif is_dict and convert_dict:
                res = {}
                tail = val
                head, tail = read_until(tail, '{')
                while tail:
                    key, tail = read_until(tail, ':')
                    val, tail = read_until(tail, ',}')
                    res[key.strip()] = procval(val.strip())
                return res
        return val

    lines = content.strip().splitlines()

    res = {}
    keyprev = ''
    indentprev = 0
    dictprev = {}
    is_multiline = False
    stack = {0: ({None: res}, None)}
    begin_multiline_indent = 0

    for line in lines:
        line_lstrip = line.lstrip()
        line_strip = line.strip()
        indent = len(line) - len(line_lstrip)
        splitted_colon = line.split(':', maxsplit = 1)
        key, val = (splitted_colon[0].strip(), splitted_colon[1].strip()) if len(splitted_colon) > 1 else ('', line_strip)
        list_val = line_strip.split('- ', maxsplit = 1)[-1]
        is_list_item = line_lstrip.startswith('- ')
        is_comment = not line_strip or line_lstrip.startswith('#')
        is_dedent = indent < indentprev
        begin_multiline = val in ['>', '|', '|>']
        is_record = len(list_val) >= 2 and list_val[0] == '{' and list_val[-1] == '}'

        if is_multiline and begin_multiline_indent and indent < begin_multiline_indent:
            is_multiline = False
            begin_multiline_indent = 0

        if not is_multiline:
            if is_list_item and indent in stack and isinstance(stack[indent][0][stack[indent][1]], dict):
                indent += 2
            if indent not in stack:
                stack[indent] = (stack[indentprev][0][stack[indentprev][1]], keyprev) if keyprev is not None else ({None: dictprev}, None)
            curdict, curkey = stack[indent]

        if is_comment:
            continue

        elif is_list_item:
            curdict[curkey] = curdict[curkey] or []
            if not key or is_record:
                curdict[curkey].append(procval(list_val))
            else:
                dictprev = {key.removeprefix('- ') : procval(val)}
                curdict[curkey].append(dictprev)
                key = None

        elif begin_multiline:
            curdict[curkey][key] = ''
            curdict, curkey = curdict[curkey], key
            is_multiline = True

        elif is_multiline:
            curdict[curkey] += ('\n' + val) if curdict[curkey] else val
            begin_multiline_indent = min(indent, begin_multiline_indent) if begin_multiline_indent else indent

        elif key and not val:
            curdict[curkey][key] = dictprev = {}

        else:
            curdict[curkey][key] = procval(val)

        if is_dedent:
            stack = {i : v for i, v in stack.items() if i <= indent}

        indentprev = indent
        keyprev = key

    return res

class NanoJekyllTemplate:
    @staticmethod
    def read_template(path, front_matter_sep = '---\n', parse_yaml = True):
        front_matter, template = '', ''
        with open(path) as f:
            line = f.readline()
            if line == front_matter_sep:
                front_matter += front_matter_sep
                while (line := f.readline()) != front_matter_sep:
                    front_matter += line
                front_matter += front_matter_sep
            else:
                template += line
            template += f.read()
        return front_matter if not parse_yaml else yaml_loads(front_matter), template

    @staticmethod
    def codegen(templates, includes = {}, global_variables = [], plugins = {}, newline = '\n'):
        indent_level = 1

        python_source  = 'import os, sys, re, html, json, datetime' + newline
        python_source += inspect.getsource(NanoJekyllContext) + newline
        python_source += ' ' * 4 * indent_level + 'includes = ' + repr(includes) + newline
        python_source += newline.join(str(NanoJekyllTemplate(template_name = template_name, template_code = template_code, includes = includes, global_variables = global_variables, indent_level = indent_level, plugins = list(plugins))) for template_name, template_code in templates.items()) + newline
        python_source += newline.join(str(Plugin(template_name = 'plugin_' + plugin_name, includes = includes, global_variables = global_variables, indent_level = indent_level)) for plugin_name, Plugin in plugins.items()) + newline
        
        try:
            global_namespace = {}
            exec(python_source, global_namespace)
            cls = global_namespace[NanoJekyllContext.__name__] 
        except Exception as e:
            print(e)
            cls = None

        return cls, python_source
  
    def __init__(self, template_name = '', template_code = '', includes = {}, global_variables = [], plugins = [], indent_level = 0):
        self.includes = includes
        self.global_variables = global_variables
        self.plugins = plugins

        self.code = []
        self.indent_level = indent_level
    
        split_tokens = lambda s: re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", s)
        # https://shopify.github.io/liquid/tags/iteration/#forloop-object

        function_name = NanoJekyllContext.sanitize_template_name(template_name)
        self.forloop_cnt = 0
        self.add_line(f'def render_{function_name}(self):')
        self.indent_level += 1
        self.add_line('''nil, empty, false, true, forloop, NanoJekyllResult = None, None, False, True, self.forloop, []''')

        filters_names = [k for k in dir(NanoJekyllContext) if (k.startswith('_') and not k.startswith('__')) and (k.endswith('_') and not k.endswith('__'))]
        self.add_line((', '.join(k.removeprefix('_').removesuffix('_') for k in filters_names) or '()') + ' = ' + ((', '.join(f'self.pipify(self.{k})' for k in filters_names) or '()')))
        self.add_line((', '.join(self.global_variables) or '()') + ' = ' +  (', '.join(NanoJekyllContext.__name__ + f'(self.ctx.get({k!r}))' for k in self.global_variables) or '()') )

        template_code = template_code or getattr(self, 'template_code', '')
        tokens = split_tokens(template_code)
        
        ops_stack = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            b = 3 if token.startswith('{%-') or token.startswith('{{-') else 2
            e = -3 if token.endswith('-%}') or token.endswith('-}}') else -2
            token_inner = token[b:e].strip()
            words = token_inner.split()
            
            if b == 3:
                self.add_line("NanoJekyllResult.append(self.NanoJekyllTrimLeft())")

            if token.startswith('{{'):
                expr = self._expr_code(token_inner)
                self.add_line(f"NanoJekyllResult.append(str({expr}))")

            elif token.startswith('{%'):
                if words[0] == '-':
                    del words[0]
                if words[-1] == '-':
                    del words[-1]

                if words[0] == 'comment':
                    tokens_i_end = tokens[i].replace(' ', '').replace('comment', 'endcomment')
                    while tokens[i].replace(' ', '') != tokens_i_end:
                        i += 1
    
                elif words[0] == 'highlight':
                    lang = ''.join(words[1:])
                    self.add_line(f'NanoJekyllResult.append("\\n```{lang}\\n")')
                    tokens_i_end = '{%endhighlight%}'
                    i += 1
                    while tokens[i].replace(' ', '') != tokens_i_end:
                        self.add_line('NanoJekyllResult.append(' + repr(tokens[i]) + ')')
                        i += 1
                    self.add_line('NanoJekyllResult.append("\\n```\\n")')
                
                elif words[0] == 'unless':
                    ops_stack.append('unless')
                    if 'contains' in words:
                        assert len(words) == 4 and words[2] == 'contains'
                        words = [words[0], words[3], 'in', words[1]]
                    self.add_line("if not( {} ):".format(' '.join(words[1:])))
                    self.indent_level += 1

                elif words[0] == 'if':
                    ops_stack.append('if')
                    if 'contains' in words:
                        assert len(words) == 4 and words[2] == 'contains'
                        words = [words[0], words[3], 'in', words[1]]
                    self.add_line("if {}:".format(' '.join(words[1:])))
                    self.indent_level += 1
                
                elif words[0] == 'elsif':
                    self.indent_level -= 1
                    self.add_line("elif {}:".format(' '.join(words[1:])))
                    self.indent_level += 1
                
                elif words[0] == 'else':
                    #ops_stack.append('else')
                    self.indent_level -= 1
                    self.add_line("else:".format(' '.join(words[1:])))
                    self.indent_level += 1
                
                elif words[0] == 'for':
                    # https://shopify.dev/docs/api/liquid/objects/forloop
                    assert len(words) in [4, 6] and words[2] == 'in', f'Dont understand for: {token=}'

                    ops_stack.append('for')
                    self.add_line('forloop_{} = list({})'.format(self.forloop_cnt, self._expr_code(words[3])))
                    if len(words) == 6 and words[4] == 'limit:':
                        self.add_line('forloop_{0} = forloop_{0}[:(int({1}) if {1} else None)]'.format(self.forloop_cnt, self._expr_code(words[5])))
                    self.add_line('for forloop.index0, {} in enumerate(forloop_{}):'.format(words[1], self.forloop_cnt))
                    self.indent_level += 1
                    self.add_line('forloop.index, forloop.rindex, forloop.rindex0, forloop.first, forloop.last, forloop.length = forloop.index0 + 1, len(forloop_{0}) - forloop.index0, len(forloop_{0}) - forloop.index0 - 1, forloop.index0 == 0, forloop.index0 == len(forloop_{0}) - 1, len(forloop_{0})'.format(self.forloop_cnt))
                    self.forloop_cnt += 1
                
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    assert len(words) == 1, f'Dont understand end: {token=}'
                    end_what = words[0][3:]
                    assert ops_stack, f'Too many ends: {token=}'
                    start_what = ops_stack.pop()
                    assert start_what == end_what, f'Mismatched end tag: {start_what=} != {end_what=}'
                    self.indent_level -= 1

                elif words[0] == 'include':
                    template_name = words[1]
                    beg = None
                    if len(words) > 2 and '=' in words:
                        beg = ([k for k, w in enumerate(words) if w == '='] or [0])[0] - 1
                        self.add_line('include=' +  NanoJekyllContext.__name__ + '(dict(' + ', '.join(words[k] + words[k + 1] + words[k + 2] for k in range(beg, len(words), 3)) + '))')
                    template_name = ' '.join(words[1:beg])

                    if '{{' not in template_name and '}}' not in template_name:
                        frontmatter_include, template_include = self.includes[template_name]
                        tokens = tokens[:i + 1] + split_tokens(template_include) + tokens[i + 1:]
                    else:
                        template_name = ' '.join(words[1:]).replace('{{', '{').replace('}}', '}')
                        template_name = 'f' + repr(template_name)
                        self.add_line('include_name = ' + template_name)
                        self.add_line('NanoJekyllResult.append(self.includes[include_name][-1])')
                
                elif words[0] == 'assign':
                    assert words[2] == '='
                    expr = self._expr_code(token_inner.split('=', maxsplit = 1)[1].strip())
                    var_name = words[1]
                    self.add_line('{} = {}'.format(var_name, expr))

                elif words[0] in plugins: 
                    template_name = words[0]
                    self.add_line(f'assert bool(self.render_plugin_{template_name}); tmp = self.render_plugin_{template_name}(); (NanoJekyllResult.extend if isinstance(tmp, list) else NanoJekyllResult.append)(tmp)')
                else:
                    assert False, ('Dont understand tag: ' + words[0])

            else:
                if token:
                    self.add_line("NanoJekyllResult.append({})".format(repr(token)))
            
            if e == -3:
                self.add_line('NanoJekyllResult.append(self.NanoJekyllTrimRight())')
            i += 1

        assert not ops_stack, ('Unmatched action tag: ' + ops_stack[-1])

        self.add_line('return self.NanoJekyllResultFinalize(NanoJekyllResult)')
    
    def _expr_code(self, expr):
        is_string_literal = lambda expr: (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'"))
        expr = expr.strip()

        if is_string_literal(expr):
             code = expr

        elif '|' in expr:
            pipes = list(map(str.strip, expr.split('|')))
            i = 0
            while i < len(pipes):
                if pipes[i].count('"') % 2 == 1:
                    pipes = pipes[:i] + [pipes[i] + ' | ' + pipes[i + 1]] + pipes[i + 2:]
                    i += 1
                i += 1

            code = NanoJekyllContext.__name__+ '(' + self._expr_code(pipes[0]) + ')' if is_string_literal(pipes[0]) else self._expr_code(pipes[0])
            for func in pipes[1:]:
                func_name, *func_args = func.split(':', maxsplit = 1)
                
                if not func_args:
                    code = f'{code} | {func_name}()'
                else:
                    assert len(func_args) == 1
                    func_args = ', '.join(map(self._expr_code, func_args[0].split(',')))
                    code = f'{code} | {func_name}({func_args})'
                    
        else:
            code = expr

        return code

    def __str__(self):
        return ''.join(map(str, self.code)) 

    def add_line(self, line = ''):
        self.code.extend([' ' * 4 * self.indent_level, line, "\n"])

class NanoJekyllContext:
    class forloop: index0, index, rindex, rindex0, first, last, length = -1, -1, -1, -1, False, False, -1
    class NanoJekyllTrimLeft(str): pass
    class NanoJekyllTrimRight(str): pass
    
    def __init__(self, ctx = None):
        # https://shopify.github.io/liquid/basics/operators/
        self.ctx = ctx.ctx if isinstance(ctx, NanoJekyllContext) else ctx
    
    def __or__(self, other):
        return NanoJekyllContext(other[0](self.ctx, *other[1:]))

    def __str__(self):
        return str(self.ctx) if self.ctx else ''

    def __bool__(self):
        return bool(self.ctx)

    def __int__(self):
        return int(self.ctx)

    def __gt__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx > other

    def __ge__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx >= other

    def __lt__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx < other

    def __le__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx <= other

    def __eq__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx == other

    def __ne__(self, other):
        other = other.ctx if isinstance(other, NanoJekyllContext) else other
        return self.ctx != other
        
    def __getattr__(self, other):
        if isinstance(self.ctx, dict):
            if other in self.ctx:
                return NanoJekyllContext(self.ctx[other])
        return NanoJekyllContext(getattr(self.ctx, other, None))
    
    def __getitem__(self, other):
        if not self.ctx:
            return NanoJekyllContext(None)
        if isinstance(self.ctx, (list, str)):
            return NanoJekyllContext(self.ctx[int(other)])
        if isinstance(self.ctx, dict):
            return NanoJekyllContext(self.ctx.get(str(other)))
        return NanoJekyllContext(None)

    def __len__(self):
        return len(self.ctx) if isinstance(self.ctx, (list, dict, str)) else None

    def __iter__(self):
        yield from (map(NanoJekyllContext, self.ctx) if self.ctx else [])

    @staticmethod
    def pipify(f):
        return (lambda *args: (f, *args))
        
    @staticmethod
    def NanoJekyllResultFinalize(result):
        # https://shopify.github.io/liquid/basics/whitespace/
        res = ''
        trimming = False
        for s in result:
            if isinstance(s, NanoJekyllContext.NanoJekyllTrimLeft):
                res = res.rstrip()
            elif isinstance(s, NanoJekyllContext.NanoJekyllTrimRight):
                trimming = True
            else:
                if trimming:
                    s = s.lstrip()
                if s:
                    res += s
                    trimming = False
        return res
    
    @staticmethod
    def sanitize_template_name(template_name):
        return os.path.splitext(template_name)[0].translate({ord('/') : '_', ord('-'): '_', ord('.') : '_'})

    def render(self, template_name, is_plugin = False):
        fn = getattr(self, ('render_' if not is_plugin else 'render_plugin_') + self.sanitize_template_name(template_name), None)
        assert fn is not None and not isinstance(fn, NanoJekyllContext)
        return fn()
    
    @property
    def first(self):
        return NanoJekyllContext(self._first_(self))
    
    @property
    def size(self):
        return NanoJekyllContext(self._size_(self))
    
    # https://shopify.github.io/liquid/basics/operators/
    # https://jekyllrb.com/docs/liquid/filters/
    
    @staticmethod
    def _first_(xs):
        # https://shopify.github.io/liquid/filters/first/
        return xs[0] if xs else None

    @staticmethod
    def _size_(xs):
        # https://shopify.github.io/liquid/filters/size/
        return len(xs) if xs else 0
    
    @staticmethod
    def _date_to_xmlschema_(dt):
        # https://jekyllrb.com/docs/liquid/filters/#date-to-xml-schema
        return str(dt) if dt else ''
    
    @staticmethod
    def _date_(dt, date_format):
        # https://shopify.github.io/liquid/filters/date/
        return str(dt) if dt else '' #.strftime(date_format)

    def _relative_url_(self, url):
        # https://jekyllrb.com/docs/liquid/filters/#relative-url
        url = str(url) if url else ''
        base_url = self.ctx.get('site', {}).get('baseurl', '')
        if base_url:
            return os.path.join('/' + base_url.lstrip('/'), url.lstrip('/'))
        return ('.' + url) if url.startswith('/') else url

    def _absolute_url_(self, url):
        # https://jekyllrb.com/docs/liquid/filters/#absolute-url
        url = str(url) if url else ''
        site_url = self.ctx.get('site', {}).get('url', '')
        base_url = self.ctx.get('site', {}).get('baseurl', '')
        if site_url:
            return os.path.join(site_url, base_url.lstrip('/'), url.lstrip('/'))
        if base_url:
            return os.path.join('/' + base_url.lstrip('/'), url.lstrip('/'))
        return ('.' + url) if url.startswith('/') else url
    
    @staticmethod
    def _jsonify_(x):
        # https://jekyllrb.com/docs/liquid/filters/#data-to-json
        return json.dumps(x, ensure_ascii = False) if x else '{}'

    @staticmethod
    def _default_(s, t):
        # https://shopify.github.io/liquid/filters/default/
        return s or t

    @staticmethod
    def _escape_(s):
        # https://shopify.github.io/liquid/filters/escape/
        # https://github.com/shopify/liquid/blob/77bc56a1c28a707c2b222559ffb0b7b1c5588928/lib/liquid/standardfilters.rb#L99
        return html.escape(str(s)) if s else ''
    
    @staticmethod
    def _xml_escape_(s):
        # https://jekyllrb.com/docs/liquid/filters/#xml-escape
        # https://github.com/jekyll/jekyll/blob/96a4198c27482f061e145953066af501d5e085e2/lib/jekyll/filters.rb#L77
        return html.escape(str(s)) if s else ''

    @staticmethod
    def _append_(xs, item):
        # https://shopify.github.io/liquid/filters/append/
        return str(xs or '') + str(item or '')

    @staticmethod
    def _join_(xs, sep = ''):
        # https://shopify.github.io/liquid/filters/join/
        return sep.join(str(x) for x in xs) if xs else ''

    @staticmethod
    def _remove_(x, y):
        # https://shopify.github.io/liquid/filters/remove/
        return x.replace(y, '') if x else ''
    
    @staticmethod
    def _strip_(x):
        # https://shopify.github.io/liquid/filters/strip/
        return str(x).strip() if x else ''

    @staticmethod
    def _normalize_whitespace_(x):
        # https://jekyllrb.com/docs/liquid/filters/#normalize-whitespace
        return ' '.join(str(x).split()) if x else ''
    
    @staticmethod
    def _strip_html_(x):
        # https://shopify.github.io/liquid/filters/strip_html/
        return re.sub(r'<[^>]+>', '', str(x)) if x else ''
    
    @staticmethod
    def _capitalize_(x):
        # https://shopify.github.io/liquid/filters/capitalize/
        return ' '.join(word.title() if i == 0 else word.lower() for i, word in enumerate(str(x).split())) if x else ''

    @staticmethod
    def _sort_(xs, key = ''):
        # https://shopify.github.io/liquid/filters/sort/
        expr = eval(f'lambda item: item.{key}') if key else None
        return sorted([NanoJekyllContext(x) for x in xs], key = expr) if xs else []
    
    @staticmethod
    def _reverse_(x):
        # https://shopify.github.io/liquid/filters/reverse/
        return list(reversed(x)) if x else ''
    
    @staticmethod
    def _where_(xs, key, value):
        # https://shopify.github.io/liquid/filters/where/
        return [x for x in xs if x.get(key, None) == value] if xs else []

    @staticmethod
    def _map_(xs, key):
        # https://shopify.github.io/liquid/filters/map/
        return [x[key] for x in xs] if xs else []
    
    @staticmethod
    def _where_exp_(xs, key, value):
        # https://jekyllrb.com/docs/liquid/filters/#where-expression
        expr = eval(f'lambda {key}: {value}', dict(nil = None, false = False, true = True))
        return [x for x in xs if expr(NanoJekyllContext(x))] if xs else []
    
    @staticmethod
    def _smartify_(x):
        # https://jekyllrb.com/docs/liquid/filters/#smartify
        return str(x) if x else ''


class NanoJekyllPluginSeo(NanoJekyllTemplate):
    template_code = '''<!-- NanoJekyll and python does not support question-marks in variable names, so replacing here ? by _ -->

<!-- Begin Jekyll SEO tag v{{ seo_tag.version }} -->
{% if seo_tag.title_ %}
  <title>{{ seo_tag.title }}</title>
{% endif %}

<meta name="generator" content="Jekyll v{{ jekyll.version }}" />

{% if seo_tag.page_title %}
  <meta property="og:title" content="{{ seo_tag.page_title }}" />
{% endif %}

{% if seo_tag.author.name %}
  <meta name="author" content="{{ seo_tag.author.name }}" />
{% endif %}

<meta property="og:locale" content="{{ seo_tag.page_locale }}" />

{% if seo_tag.description %}
  <meta name="description" content="{{ seo_tag.description }}" />
  <meta property="og:description" content="{{ seo_tag.description }}" />
  <meta property="twitter:description" content="{{ seo_tag.description }}" />
{% endif %}

{% if site.url %}
  <link rel="canonical" href="{{ seo_tag.canonical_url }}" />
  <meta property="og:url" content="{{ seo_tag.canonical_url }}" />
{% endif %}

{% if seo_tag.site_title %}
  <meta property="og:site_name" content="{{ seo_tag.site_title }}" />
{% endif %}

{% if seo_tag.image %}
  <meta property="og:image" content="{{ seo_tag.image.path }}" />
  {% if seo_tag.image.height %}
    <meta property="og:image:height" content="{{ seo_tag.image.height }}" />
  {% endif %}
  {% if seo_tag.image.width %}
    <meta property="og:image:width" content="{{ seo_tag.image.width }}" />
  {% endif %}
  {% if seo_tag.image.alt %}
    <meta property="og:image:alt" content="{{ seo_tag.image.alt }}" />
  {% endif %}
{% endif %}

{% if page.date %}
  <meta property="og:type" content="article" />
  <meta property="article:published_time" content="{{ page.date | date_to_xmlschema }}" />
{% else %}
  <meta property="og:type" content="website" />
{% endif %}

{% if paginator.previous_page %}
  <link rel="prev" href="{{ paginator.previous_page_path | absolute_url }}" />
{% endif %}
{% if paginator.next_page %}
  <link rel="next" href="{{ paginator.next_page_path | absolute_url }}" />
{% endif %}

{% if seo_tag.image %}
  <meta name="twitter:card" content="{{ page.twitter.card | default: site.twitter.card | default: "summary_large_image" }}" />
  <meta property="twitter:image" content="{{ seo_tag.image.path }}" />
{% else %}
  <meta name="twitter:card" content="summary" />
{% endif %}

{% if seo_tag.image.alt %}
  <meta name="twitter:image:alt" content="{{ seo_tag.image.alt }}" />
{% endif %}

{% if seo_tag.page_title %}
  <meta property="twitter:title" content="{{ seo_tag.page_title }}" />
{% endif %}

{% if site.twitter %}
  <meta name="twitter:site" content="@{{ site.twitter.username | remove:'@' }}" />

  {% if seo_tag.author.twitter %}
    <meta name="twitter:creator" content="@{{ seo_tag.author.twitter | remove:'@' }}" />
  {% endif %}
{% endif %}

{% if site.facebook %}
  {% if site.facebook.admins %}
    <meta property="fb:admins" content="{{ site.facebook.admins }}" />
  {% endif %}

  {% if site.facebook.publisher %}
    <meta property="article:publisher" content="{{ site.facebook.publisher }}" />
  {% endif %}

  {% if site.facebook.app_id %}
    <meta property="fb:app_id" content="{{ site.facebook.app_id }}" />
  {% endif %}
{% endif %}

{% if site.webmaster_verifications %}
  {% if site.webmaster_verifications.google %}
    <meta name="google-site-verification" content="{{ site.webmaster_verifications.google }}" />
  {% endif %}

  {% if site.webmaster_verifications.bing %}
    <meta name="msvalidate.01" content="{{ site.webmaster_verifications.bing }}" />
  {% endif %}

  {% if site.webmaster_verifications.alexa %}
    <meta name="alexaVerifyID" content="{{ site.webmaster_verifications.alexa }}" />
  {% endif %}

  {% if site.webmaster_verifications.yandex %}
    <meta name="yandex-verification" content="{{ site.webmaster_verifications.yandex }}" />
  {% endif %}

  {% if site.webmaster_verifications.baidu %}
    <meta name="baidu-site-verification" content="{{ site.webmaster_verifications.baidu }}" />
  {% endif %}

  {% if site.webmaster_verifications.facebook %}
    <meta name="facebook-domain-verification" content="{{ site.webmaster_verifications.facebook }}" />
  {% endif %}
{% elsif site.google_site_verification %}
  <meta name="google-site-verification" content="{{ site.google_site_verification }}" />
{% endif %}

<script type="application/ld+json">
  {{ seo_tag.json_ld | jsonify }}
</script>

<!-- End Jekyll SEO tag -->
'''

class NanoJekyllPluginFeedMeta(NanoJekyllTemplate):
    template_code = '''
<link type="application/atom+xml" rel="alternate" href='{{ site.feed.path | default: "feed.xml" }}' title="{{ site.title }}" />
'''
    #def __str__(self): return ' ' * 4 * self.indent_level + 'def render_{template_name}(self):\n'.format(template_name = self.template_name) + self.template_code.replace('{{ site.feed.path | default: "feed.xml" }}', self._default_(str(self.site.feed.path), "feed.xml")).replace('{{ site.title }}', str(self.page.title))'''


class NanoJekyllPluginFeedMetaXml(NanoJekyllTemplate):
    # https://github.com/jekyll/jekyll-feed/blob/master/lib/jekyll-feed/feed.xml
    template_code = '''
<?xml version="1.0" encoding="utf-8"?>
{% if page.xsl %}
  <?xml-stylesheet type="text/xml" href="{{ '/feed.xslt.xml' | absolute_url }}"?>
{% endif %}
<feed xmlns="http://www.w3.org/2005/Atom" {% if site.lang %}xml:lang="{{ site.lang }}"{% endif %}>
  <generator uri="https://jekyllrb.com/" version="{{ jekyll.version }}">Jekyll</generator>
  <link href="{{ page.url | absolute_url }}" rel="self" type="application/atom+xml" />
  <link href="{{ '/' | absolute_url }}" rel="alternate" type="text/html" {% if site.lang %}hreflang="{{ site.lang }}" {% endif %}/>
  <updated>{{ site.time | date_to_xmlschema }}</updated>
  <id>{{ page.url | absolute_url | xml_escape }}</id>

  {% assign title = site.title | default: site.name %}
  {% if page.collection != "posts" %}
    {% assign collection = page.collection | capitalize %}
    {% assign title = title | append: " | " | append: collection %}
  {% endif %}
  {% if page.category %}
    {% assign category = page.category | capitalize %}
    {% assign title = title | append: " | " | append: category %}
  {% endif %}

  {% if title %}
    <title type="html">{{ title | smartify | xml_escape }}</title>
  {% endif %}

  {% if site.description %}
    <subtitle>{{ site.description | xml_escape }}</subtitle>
  {% endif %}

  {% if site.author %}
    <author>
        <name>{{ site.author.name | default: site.author | xml_escape }}</name>
      {% if site.author.email %}
        <email>{{ site.author.email | xml_escape }}</email>
      {% endif %}
      {% if site.author.uri %}
        <uri>{{ site.author.uri | xml_escape }}</uri>
      {% endif %}
    </author>
  {% endif %}

  {% if page.tags %}
    {% assign posts = site.tags[page.tags] %}
  {% else %}
    {% assign posts = site[page.collection] %}
  {% endif %}
  {% if page.category %}
    {% assign posts = posts | where: "categories", page.category %}
  {% endif %}
  {% unless site.show_drafts %}
    {% assign posts = posts | where_exp: "post", "post.draft != true" %}
  {% endunless %}
  {% assign posts = posts | sort: "date" | reverse %}
  {% assign posts_limit = site.feed.posts_limit | default: 10 %}
  {% for post in posts limit: posts_limit %}
    <entry{% if post.lang %}{{" "}}xml:lang="{{ post.lang }}"{% endif %}>
      {% assign post_title = post.title | smartify | strip_html | normalize_whitespace | xml_escape %}

      <title type="html">{{ post_title }}</title>
      <link href="{{ post.url | absolute_url }}" rel="alternate" type="text/html" title="{{ post_title }}" />
      <published>{{ post.date | date_to_xmlschema }}</published>
      <updated>{{ post.last_modified_at | default: post.date | date_to_xmlschema }}</updated>
      <id>{{ post.id | absolute_url | xml_escape }}</id>
      {% assign excerpt_only = post.feed.excerpt_only | default: site.feed.excerpt_only %}
      {% unless excerpt_only %}
        <content type="html" xml:base="{{ post.url | absolute_url | xml_escape }}"><![CDATA[{{ post.content | strip }}]]></content>
      {% endunless %}

      {% assign post_author = post.author | default: post.authors[0] | default: site.author %}
      {% assign post_author = site.data.authors[post_author] | default: post_author %}
      {% assign post_author_email = post_author.email | default: nil %}
      {% assign post_author_uri = post_author.uri | default: nil %}
      {% assign post_author_name = post_author.name | default: post_author %}

      <author>
          <name>{{ post_author_name | default: "" | xml_escape }}</name>
        {% if post_author_email %}
          <email>{{ post_author_email | xml_escape }}</email>
        {% endif %}
        {% if post_author_uri %}
          <uri>{{ post_author_uri | xml_escape }}</uri>
        {% endif %}
      </author>

      {% if post.category %}
        <category term="{{ post.category | xml_escape }}" />
      {% elsif post.categories %}
        {% for category in post.categories %}
          <category term="{{ category | xml_escape }}" />
        {% endfor %}
      {% endif %}

      {% for tag in post.tags %}
        <category term="{{ tag | xml_escape }}" />
      {% endfor %}

      {% assign post_summary = post.description | default: post.excerpt %}
      {% if post_summary and post_summary != empty %}
        <summary type="html"><![CDATA[{{ post_summary | strip_html | normalize_whitespace }}]]></summary>
      {% endif %}

      {% assign post_image = post.image.path | default: post.image %}
      {% if post_image %}
        {% unless post_image contains "://" %}
          {% assign post_image = post_image | absolute_url %}
        {% endunless %}
        <media:thumbnail xmlns:media="http://search.yahoo.com/mrss/" url="{{ post_image | xml_escape }}" />
        <media:content medium="image" url="{{ post_image | xml_escape }}" xmlns:media="http://search.yahoo.com/mrss/" />
      {% endif %}
    </entry>
  {% endfor %}
</feed>
'''
