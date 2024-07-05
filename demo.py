import os
import json
import argparse
import markdown
import datetime

import nanojekyll

markdown_extensions = ['meta', 'tables', 'toc']

def read_template(path, render = True):
    frontmatter, content = nanojekyll.NanoJekyllTemplate.read_template(path)
    if path.endswith('.md') and render:
        content = markdown.markdown(content, extensions = markdown_extensions)
    return frontmatter, content

def render(cls, ctx = {}, content = '', template_name = '', templates = {}):
    # https://jekyllrb.com/docs/rendering-process/
    while template_name:
        frontmatter, template = [l for k,l in templates.items() if k == template_name or os.path.splitext(k)[0] == template_name][0] 
        content = cls(ctx | dict(content = content)).render(template_name)
        template_name = frontmatter.get('layout')
    return content

def get_page_date(page_path, date_template = '0000-00-00'):
    page_name = os.path.basename(page_path)
    if len(page_name) >= len(date_template) and page_name[:4].isdigit() and page_name[5:7].isdigit() and page_name[8:10].isdigit() and page_name[4] == page_name[7] == '-':
        return page_name[:len(date_template)]
    return ''

def build_context(config, siteurl = '', baseurl = '', dynamic_assets = {}, pages = {}, posts = {}):
    ctx = dict(site = config, jekyll = dict(environment = 'production'), paginator = {})
    ctx['site'].update(dict(
        url = siteurl,
        baseurl = baseurl,
        feed = dict(path = 'feed.xml', excerpt_only = False),
        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        header_pages = ctx['site'].get('header_pages', []) or [k for k in pages if not k.startswith('404.') and not k.startswith('index.')]
    ))

    ctx['assets_pages_posts'] = {}
    for input_path, output_path in list(dynamic_assets.items()) + list(pages.items()) + list(posts.items()):
        frontmatter, content = read_template(input_path, render = False)
        content_lines = content.strip().splitlines()
        title_from_id = os.path.splitext(os.path.basename(input_path))[0].removeprefix(get_page_date(input_path)).strip('-').strip('_').replace('-', ' ').replace('_', ' ').title()
        title_from_content = content_lines[0].removeprefix('### ').removeprefix('## ').removeprefix('# ').strip() if content_lines and (content_lines[0].startswith('### ') or content_lines[0].startswith('## ') or content_lines[0].startswith('# ')) else ''
        
        ctx['page'] = dict(
            type         = 'page' if input_path in pages else 'post' if input_path in posts else 'asset',
            url          = os.path.basename(output_path), 
            id           = input_path,
            content      = content,
            excerpt      = content[:500] + '...',
            lang         = ctx['site'].get('lang', 'en'),
            locale       = ctx['site'].get('locale', 'en_US'),
            layout       = 'default',
            description  = '',
            path         = input_path,
            title        = title_from_content or title_from_id,
            date         = get_page_date(input_path),
            twitter      = dict(card = 'summary_large_image'),
            image        = dict(path = 'path', height = '0', width = '0', alt = ''),
        ) | frontmatter

        ctx['page']['seo_tag'] = dict(
            page_locale    = ctx['page'].get('locale', '') or ctx['site'].get('locale', '') or 'en_US',
            description    = ctx['page'].get('description', '') or ctx['site'].get('description', ''),
            site_title     = ctx['site'].get('title', ''), 
            page_title     = ctx['page'].get('title', ''),
            title          = ctx['page'].get('title', '') or ctx['site'].get('title', ''),
            author         = ctx['site'].get('author', {}),
            image          = ctx['page']['image'],
            canonical_url  = os.path.join(ctx['site'].get('url', ''), ctx['site'].get('baseurl', '').lstrip('/' * bool(ctx['site'].get('url', ''))), ctx['page']['url']), # https://mademistakes.com/mastering-jekyll/site-url-baseurl/
        )

        ctx['page']['seo_tag']['json_ld'] = {
            '@context'     : 'https://schema.org',
            '@type'        : 'WebPage',
            'description'  : ctx['page']['seo_tag']['description'],
            'url'          : ctx['page']['seo_tag']['canonical_url'],
            'headline'     : ctx['page']['seo_tag']['page_title'],
            'name'         : ctx['page']['seo_tag']['site_title'],
            'author'       : {'@type' : 'Person', 'name': ctx['site'].get('author', {}).get('name', ''), 'email' : ctx['site'].get('author', {}).get('email', '')}
        }
        ctx['assets_pages_posts'][input_path] = ctx.pop('page')
    ctx['site']['pages'] = [ctx['assets_pages_posts'][k] for k in pages.keys()]
    ctx['site']['posts'] = [ctx['assets_pages_posts'][k] for k in posts.keys()]
    return ctx

def main(
    config_yml,
    output_dir,
    layouts_dir,
    includes_dir,
    icons_dir,
    codegen_py,
    siteurl,
    baseurl,
    includes_basenames,
    icons_basenames,
    layouts_basenames,
    global_variables,
    static_assets,
    dynamic_assets,
    pages,
    posts
):
    static_assets = dict(a.split('=') for a in static_assets)
    dynamic_assets = dict(a.split('=') for a in dynamic_assets)
    pages = dict(a.split('=') for a in pages)
    posts = dict(a.split('=') for a in posts)

    #####################################

    config = nanojekyll.yaml_loads(open(config_yml).read())
    ctx = build_context(config, siteurl = siteurl, baseurl = baseurl, dynamic_assets = dynamic_assets, pages = pages, posts = posts)


    icons = {os.path.join(os.path.basename(icons_dir), basename) : ({}, open(os.path.join(icons_dir, basename)).read()) for basename in icons_basenames} 

    templates_layouts = {os.path.splitext(basename)[0] : read_template(os.path.join(layouts_dir, basename)) for basename in layouts_basenames} 
    templates_includes = {basename: read_template(os.path.join(includes_dir, basename)) for basename in includes_basenames}
    templates_pages = {input_path: read_template(input_path) for input_path in pages}
    templates_posts = {input_path: read_template(input_path) for input_path in posts}
    templates_assets = {input_path : read_template(input_path) for input_path in dynamic_assets}

    templates_all = (templates_includes | templates_layouts | templates_pages | templates_posts | templates_assets)
    cls, python_source = nanojekyll.NanoJekyllTemplate.codegen({k : v[1] for k, v in templates_all.items()}, includes = templates_includes | icons, global_variables = global_variables, plugins = {'seo': nanojekyll.NanoJekyllPluginSeo, 'feed_meta' : nanojekyll.NanoJekyllPluginFeedMeta, 'feed_meta_xml' : nanojekyll.NanoJekyllPluginFeedMetaXml})
    with open(codegen_py, 'w') as f:
        f.write(python_source)
    #cls = __import__('nanojekyllcodegen').NanoJekyllContext
    print(codegen_py)

    assert cls

    os.makedirs(output_dir, exist_ok = True)
    print(output_dir)

    for input_path, output_path in static_assets.items():
        output_path = os.path.join(output_dir, output_path or input_path)
        os.makedirs(os.path.dirname(output_path), exist_ok = True)
        with open(output_path, 'wb') as f, open(input_path, 'rb') as g:
            content = g.read()
            f.write(content)
        print(output_path)

    for input_path, output_path in list(dynamic_assets.items()) + list(pages.items()) + list(posts.items()):
        output_path = os.path.join(output_dir, output_path or input_path)
        os.makedirs(os.path.dirname(output_path), exist_ok = True)
        
        ctx['page'] = ctx['assets_pages_posts'][input_path]
        ctx['seo_tag'] = ctx['page']['seo_tag']
        with open(output_path, 'w') as f:
            f.write(render(cls, ctx, template_name = input_path, templates = templates_all))
        print(output_path)

    if output_path := ctx['site'].get('feed', {}).get('path', ''):
        output_path = os.path.join(output_dir, output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok = True)
        
        ctx['page'] = dict(collection = 'posts', url = os.path.join(ctx['site'].get('url', ''), ctx['site'].get('baseurl', '').lstrip('/' * bool(ctx['site'].get('url', ''))), output_path))
        with open(output_path, 'w') as f:
            content = cls(ctx).render('feed_meta_xml', is_plugin = True)
            f.write(content)
        print(output_path)
    

#####################################

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-yml', default = '_config.yml')
    parser.add_argument('--output-dir', default = '_site')
    parser.add_argument('--layouts-dir', default = '_layouts')
    parser.add_argument('--includes-dir', default = '_includes')
    parser.add_argument('--icons-dir', default = '_includes/social-icons')
    parser.add_argument('--codegen-py', default = 'nanojekyllcodegen.py')
    parser.add_argument('--siteurl', default = '.')
    parser.add_argument('--baseurl', default = '')
    parser.add_argument('--includes-basenames', nargs = '*', default = ['footer.html', 'head.html', 'custom-head.html', 'social.html', 'social-item.html', 'svg_symbol.html', 'google-analytics.html',   'header.html', 'disqus_comments.html'])
    parser.add_argument('--icons-basenames', nargs = '*', default = ['devto.svg', 'flickr.svg', 'google_scholar.svg', 'linkedin.svg', 'pinterest.svg', 'telegram.svg', 'youtube.svg', 'dribbble.svg', 'github.svg', 'instagram.svg', 'mastodon.svg', 'rss.svg', 'twitter.svg', 'facebook.svg', 'gitlab.svg', 'keybase.svg', 'microdotblog.svg', 'stackoverflow.svg', 'x.svg'])
    parser.add_argument('--layouts-basenames', nargs = '*', default = ['base.html', 'page.html', 'post.html', 'home.html'])
    parser.add_argument('--global-variables', nargs = '*', default = ['site', 'page', 'layout', 'theme', 'content', 'paginator', 'jekyll', 'seo_tag']) # https://jekyllrb.com/docs/variables/
    
    parser.add_argument('--static-assets', nargs = '*', default = ['assets/css/style.css=assets/css/style.css'])
    parser.add_argument('--dynamic-assets', nargs = '*', default = ['assets/minima-social-icons.liquid=assets/minima-social-icons.svg'])
    
    parser.add_argument('--pages', nargs = '*', default = ['404.html=404.html', 'index.md=index.html', 'about.md=about.html'])
    parser.add_argument('--posts', nargs = '*', default = ['_posts/2016-05-19-super-short-article.md=2016-05-19-super-short-article.html', '_posts/2016-05-20-super-long-article.md=2016-05-20-super-long-article.html', '_posts/2016-05-20-welcome-to-jekyll.md=2016-05-20-welcome-to-jekyll.html', '_posts/2016-05-20-my-example-post.md=2016-05-20-my-example-post.html', '_posts/2016-05-20-this-post-demonstrates-post-content-styles.md=2016-05-20-this-post-demonstrates-post-content-styles.html'])

    args = parser.parse_args()

    main(**vars(args))
