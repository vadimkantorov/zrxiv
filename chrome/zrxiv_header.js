var zrxiv_document_id = new RegExp('abs/(\\d+\.\\d+)', 'g').exec(window.location.href)[1];
var zrxiv_root = document.getElementById('zrxiv') || {getAttribute : x => ''};
var zrxiv_github_username_token = zrxiv_root.getAttribute('zrxiv_github_username_token');
var zrxiv_github_api = zrxiv_root.getAttribute('zrxiv_github_api');
var zrxiv_site = zrxiv_root.getAttribute('zrxiv_site');

function zrxiv_tag_add()
{
	var tag = document.getElementById('zrxiv_tag').value;
	fetch(zrxiv_github_api + '/contents/_data/tags/' + tag + '.txt',
	{
		method : 'put',
		headers : {
			'Content-Type' : 'application/json',
			'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)
		},
		body : JSON.stringify({message : 'Create tag ' + tag, content : '' })
	})
	.then(res => zrxiv_tag_changed(null, tag, true))
	.then(res => {
		document.getElementById('zrxiv_tags').appendChild(zrxiv_make_checkbox(tag, true));
		document.getElementById('zrxiv_tag').value = '';
	});
}

function zrxiv_tag_changed(checkbox, tag, checked)
{
	if(checkbox != null)
	{
		tag = checkbox.value;
		checked = checkbox.checked;
	}

	return fetch(zrxiv_github_api + '/contents/_data/documents/' + zrxiv_document_id + '.json', { headers : {'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)}})
	.then(res => res.json())
	.then(res =>
	{
		var doc = JSON.parse(atob(res.content));
		doc.tags = doc.tags || [];

		var checked_old = doc.tags.indexOf(tag) != -1;
		if(checked && !checked_old)
			doc.tags.push(tag);
		else if(!checked && checked_old)
			doc.tags = doc.tags.filter(x => x != tag);
		
		fetch(zrxiv_github_api + '/contents/_data/documents/' + zrxiv_document_id + '.json',
		{
			method : 'put',
			headers : {
				'Content-Type' : 'application/json',
				'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)
			},
			body : JSON.stringify({sha : res.sha, message : 'Change tag of ' + zrxiv_document_id, content : btoa(JSON.stringify(doc)) })
		});
	});
}

function zrxiv_tags_render(tags_on)
{
	return fetch(zrxiv_github_api + '/contents/_data/tags', { headers : {'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)} })
	.then(res => res.json())
	.then(res => {
		var tags_all = res.map(x => x.name.split('.').slice(0, -1).join('.'));
		var tags = document.getElementById('zrxiv_tags');
		tags.innerHTML = '';
		for(var i = 0; i < tags_all.length; i++)
			tags.appendChild(zrxiv_make_checkbox(tags_all[i], tags_on.indexOf(tags_all[i]) != -1))
	})
}

function zrxiv_document_add()
{
	var zrxiv_tag = document.getElementById('zrxiv_tag'), zrxiv_tag_add = document.getElementById('zrxiv_tag_add');
	zrxiv_tag.addEventListener('keyup', function(event)
	{
		event.preventDefault();
		if (event.keyCode === 13)
			zrxiv_tag_add.click();
	});
	document.getElementById('zrxiv_site').href = zrxiv_site;

	fetch(zrxiv_github_api + '/contents/_data/documents/' + zrxiv_document_id + '.json',
	{
		method : 'put',
		headers : {
			'Content-Type' : 'application/json',
			'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)
		},
		body : JSON.stringify({ message : 'Add ' + zrxiv_document_id, content : btoa(JSON.stringify({id : zrxiv_document_id, title : document.title, url : window.location.href, date : Math.floor(new Date().getTime() / 1000), tags : [] })) })
	})
	.then(res => 
	{
		if(res.statusCode == 200)
			return [];
		else
			return fetch(zrxiv_github_api + '/contents/_data/documents/' + zrxiv_document_id + '.json', { headers : {'Authorization' : 'Basic ' + btoa(zrxiv_github_username_token)}}).then(res => res.json()).then(res => JSON.parse(atob(res.content)).tags || []);
	})
	.then(zrxiv_tags_render);
}

function zrxiv_make_checkbox(tag, checked)
{
	var checkbox = document.createElement('input');
	checkbox.type = 'checkbox'
	checkbox.value = tag;
	checkbox.checked = checked,
	checkbox.addEventListener('change', function() { zrxiv_tag_changed(this); });
	var label = document.createElement('label');
	label.appendChild(checkbox);
	label.appendChild(document.createTextNode(tag));
	return label;
}

if(!document.getElementById('zrxiv'))
{
	fetch(chrome.extension.getURL('zrxiv_header.html'))
	.then(response => response.text())
	.then(data => { chrome.storage.sync.get({zrxiv_github_repo: null, zrxiv_github_token: null}, function(options) {
		if(options.zrxiv_github_repo == null || options.zrxiv_github_token == null)
			return;

		var container = document.createElement('div');
		container.id = 'zrxiv';

		var match = new RegExp('github.com/(.+)/(.+)', 'g').exec(options.zrxiv_github_repo);
		var username = match[1], repo = match[2];
		container.innerHTML = data;
		container.setAttribute('zrxiv_github_username_token', username + ':' + options.zrxiv_github_token);
		container.setAttribute('zrxiv_github_api',options.zrxiv_github_repo.replace('github.com', 'api.github.com/repos'));
		container.setAttribute('zrxiv_site', options.zrxiv_github_repo.replace('github.com/' + username, username + '.github.io'));

		document.body.insertBefore(container, document.body.firstChild);
		var script = document.createElement('script');
		script.type = 'text/javascript';
		script.src = chrome.extension.getURL('zrxiv_header.js');
		document.body.appendChild(script);
	});	});
}
else
{
	if(zrxiv_github_api)
		zrxiv_document_add();
}
