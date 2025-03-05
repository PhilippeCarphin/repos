function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

let shouldPrint = function(r, show_ignored){
    if(r.State.Dirty || r.State.UnstagedChanges
       || r.State.UntrackedFiles != 0 || r.State.UntrackedDirs != 0) {
        return true;
    }
    if(r.State.RemoteState.Ahead > 0 || r.State.RemoteState.Behind > 0) {
        return !r.Config.Ignore || show_ignored
    }
    return false
}

let reposServerRequest = function(){
    let req = new XMLHttpRequest();
    req.onreadystatechange = function(){
        if(this.readyState != 4){return;}
        if(this.status != 200){console.log(this); return;}

        let all_button = document.getElementById("repos-control-all")
        let ignore_button = document.getElementById("repos-control-ignore")
        resp = JSON.parse(this.responseText);
        highlighted = syntaxHighlight(JSON.stringify(resp, undefined, 2))
        document.getElementById('repos-server-response').innerHTML = highlighted
        let table = document.getElementById("repos-table-body")
        table.innerHTML = ""
        resp.sort((r,s) => {
            const nr = r.Config.Name.toUpperCase();
            const ns = s.Config.Name.toUpperCase();
            if(nr < ns){
                return -1;
            } else if (nr > ns){
                return 1;
            } else {
                return 0;
            }
        })
        resp.forEach( (r) => {
            if(!all_button.checked && !shouldPrint(r, ignore_button.checked)){
                return // it's a callback so this is a continue
            }
            let row = document.createElement("tr")
            table.appendChild(row)
            let branch = r.State.CurrentBranch
            if(branch.startsWith("((")){
                branch = `<td class="repo-hash">${r.State.CurrentBranch}</td>`
            } else {
                branch = `<td class="repo-branch">${r.State.CurrentBranch}</td>`
            }
            let ahead = ""
            let behind = ""
            if(r.State.RemoteState.Ahead > 0){
                ahead = `+${r.State.RemoteState.Ahead}`
            }
            if(r.State.RemoteState.Behind > 0) {
                behind = `-${r.State.RemoteState.Behind}`
            }
            let stagedChanges = ""
            let unstagedChanges = ""
            if(r.State.StagedChanges) {
                stagedChanges = `(${r.State.StagedFiles}f, +${r.State.StagedInsertions}, -${r.State.StagedDeletions})`
            }
            if(r.State.Dirty) {
                unstagedChanges = `(${r.State.Files}f, +${r.State.Insertions}, -${r.State.Deletions})`
            }
            let untrackedFiles = ""
            if(r.State.UntrackedFiles || r.State.UntrackedDirs){
                untrackedFiles = `${r.State.UntrackedDirs}d,${r.State.UntrackedFiles}f`
            }
            let timeSinceLastCommit = r.State.TimeSinceLastCommit / 3600000000000
            timeSinceLastCommit = timeSinceLastCommit.toFixed(2)
            row.innerHTML = `<td class="repo-name">${r.Config.Name}</td>
                             ${branch}
                             <td class="repo-remote-state">${ahead}${behind}</td>
                             <td class="repo-staged-changes">${stagedChanges}</td>
                             <td class="repo-unstaged-changes">${unstagedChanges}</td>
                             <td class="repo-untracked-files">${untrackedFiles}</td>
                             <td class="repo-time-since-last-commit">${timeSinceLastCommit} hours</td>`
        })
    };

    req.open('GET', '/repos-server/repos-data');
    req.send();
};
