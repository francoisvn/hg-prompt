#!/usr/bin/env python

'''get repository information for use in a shell prompt

Take a string, parse any special variables inside, and output the result.

Useful mostly for putting information about the current repository into
a shell prompt.
'''

from __future__ import with_statement, print_function

import re
import os
import subprocess
from datetime import datetime, timedelta
from contextlib import closing
from os import path
from mercurial import extensions, commands, cmdutil, help
from mercurial.node import hex, short

# command registration moved into `registrar` module in v4.3.
cmdtable = {}
try:
    from mercurial import registrar
    command = registrar.command(cmdtable)
except (ImportError, AttributeError) as e:
    command = cmdutil.command(cmdtable)

# `revrange' has been moved into module `scmutil' since v1.9.
try :
    from mercurial import scmutil
    revrange = scmutil.revrange
except :
    revrange = cmdutil.revrange

FILTER_ARG = re.compile(r'\|.+\((.*)\)')

def _with_groups(groups, out):
    out_groups = [groups[0]] + [groups[-1]]

    if any(out_groups) and not all(out_groups):
        print ('Error parsing prompt string.  Mismatched braces?')

    out = s(out)
    out = out.replace('%', '%%')
    return ("%s" + out + "%s") % (out_groups[0][:-1] if out_groups[0] else '',
                                  out_groups[1][1:] if out_groups[1] else '')

def _get_filter(name, g):
    '''Return the filter with the given name, or None if it was not used.'''
    matching_filters = list(filter(lambda s: s and s.startswith('|%s' % name), g))
    if not matching_filters:
        return None

    # Later filters will override earlier ones, for now.
    f = matching_filters[-1]

    return f

def _get_filter_arg(f):
    if not f:
        return None

    args = FILTER_ARG.match(f).groups()
    if args:
        return args[0]
    else:
        return None

def b(s):
    return bytes(s.encode("utf-8"))

def s(b):
    return b.decode("utf-8")

@command(b('prompt'),
         [(b(''), b('angle-brackets'), None, b('use angle brackets (<>) for keywords'))],
         b('hg prompt STRING'))
def prompt(ui, repo, fs=b(''), **opts):
    '''get repository information for use in a shell prompt

    Take a string and output it for use in a shell prompt. You can use
    keywords in curly braces::

        $ hg prompt "currently on {branch}"
        currently on default

    You can also use an extended form of any keyword::

        {optional text here{keyword}more optional text}

    This will expand the inner {keyword} and output it along with the extra
    text only if the {keyword} expands successfully.  This is useful if you
    have a keyword that may not always apply to the current state and you
    have some text that you would like to see only if it is appropriate::

        $ hg prompt "currently at {bookmark}"
        currently at
        $ hg prompt "{currently at {bookmark}}"
        $ hg bookmark my-bookmark
        $ hg prompt "{currently at {bookmark}}"
        currently at my-bookmark

    See 'hg help prompt-keywords' for a list of available keywords.

    The format string may also be defined in an hgrc file::

        [prompt]
        template = {currently at {bookmark}}

    This is used when no format string is passed on the command line.
    '''

    def _basename(m):
        return _with_groups(m.groups(), path.basename(repo.root)) if repo.root else ''

    def _bookmark(m):
        try:
            book = extensions.find(b('bookmarks')).current(repo)
        except AttributeError:
            book = getattr(repo, '_bookmarkcurrent', None)
        except KeyError:
            book = getattr(repo, '_bookmarkcurrent', None)
        if book is None:
            book = getattr(repo, '_activebookmark', None)
        if book:
            cur = repo[b('.')].node()
            if repo._bookmarks[book] == cur:
                return _with_groups(m.groups(), book)
        else:
            return ''

    def _branch(m):
        g = m.groups()

        branch = repo.dirstate.branch()
        quiet = _get_filter('quiet', g)

        out = branch if (not quiet) or (branch != 'default') else ''

        return _with_groups(g, out) if out else ''

    def _closed(m):
        g = m.groups()

        quiet = _get_filter('quiet', g)

        p = repo[None].parents()[0]
        pn = p.node()
        branch = repo.dirstate.branch()
        closed = (p.extra().get(b('close'))
                  and pn in repo.branchheads(branch, closed=True))
        out = b('X') if (not quiet) and closed else ''

        return _with_groups(g, out) if out else ''

    def _count(m):
        g = m.groups()
        query = [b(g[1][1:])] if g[1] else [b('all()')]
        return _with_groups(g, b("%d" % len(revrange(repo, query))))

    def _node(m):
        g = m.groups()

        parents = repo[None].parents()
        p = 0 if '|merge' not in g else 1
        p = p if len(parents) > p else None

        format = short if '|short' in g else hex

        node = format(parents[p].node()) if p is not None else None
        return _with_groups(g, node) if node else ''

    def _patch(m):
        g = m.groups()

        try:
            extensions.find(b('mq'))
        except KeyError:
            return ''

        q = repo.mq

        if _get_filter('quiet', g) and not len(q.series):
            return ''

        if _get_filter('topindex', g):
            if len(q.applied):
                out = b('%d' % (len(q.applied) - 1))
            else:
                out = b('')
        elif _get_filter('applied', g):
            out = b('%d' % len(q.applied))
        elif _get_filter('unapplied', g):
            out = b('%d' % len(q.unapplied(repo)))
        elif _get_filter('count', g):
            out = b('%d' % len(q.series))
        else:
            out = q.applied[-1].name if q.applied else b('')

        return _with_groups(g, out) if out else ''

    def _patches(m):
        g = m.groups()

        try:
            extensions.find(b('mq'))
        except KeyError:
            return ''

        join_filter = _get_filter('join', g)
        join_filter_arg = _get_filter_arg(join_filter)
        sep = b(join_filter_arg) if join_filter else b(' -> ')

        patches = repo.mq.series
        applied = [p.name for p in repo.mq.applied]
        unapplied = list(filter(lambda p: p not in applied, patches))

        if _get_filter('hide_applied', g):
            patches = list(filter(lambda p: p not in applied, patches))
        if _get_filter('hide_unapplied', g):
            patches = list(filter(lambda p: p not in unapplied, patches))

        if _get_filter('reverse', g):
            patches = list(reversed(patches))

        pre_applied_filter = _get_filter('pre_applied', g)
        pre_applied_filter_arg = _get_filter_arg(pre_applied_filter)
        post_applied_filter = _get_filter('post_applied', g)
        post_applied_filter_arg = _get_filter_arg(post_applied_filter)

        pre_unapplied_filter = _get_filter('pre_unapplied', g)
        pre_unapplied_filter_arg = _get_filter_arg(pre_unapplied_filter)
        post_unapplied_filter = _get_filter('post_unapplied', g)
        post_unapplied_filter_arg = _get_filter_arg(post_unapplied_filter)

        if pre_applied_filter_arg:
            pre_applied_filter_arg = b(pre_applied_filter_arg)

        if post_applied_filter_arg:
            post_applied_filter_arg = b(post_applied_filter_arg)

        if pre_unapplied_filter_arg:
            pre_unapplied_filter_arg = b(pre_unapplied_filter_arg)

        if post_unapplied_filter_arg:
            post_unapplied_filter_arg = b(post_unapplied_filter_arg)

        for n, patch in enumerate(patches):
            if patch in applied:
                if pre_applied_filter:
                    patches[n] = pre_applied_filter_arg + patches[n]
                if post_applied_filter:
                    patches[n] = patches[n] + post_applied_filter_arg
            elif patch in unapplied:
                if pre_unapplied_filter:
                    patches[n] = pre_unapplied_filter_arg + patches[n]
                if post_unapplied_filter:
                    patches[n] = patches[n] + post_unapplied_filter_arg

        return _with_groups(g, sep.join(patches)) if patches else ''

    def _queue(m):
        g = m.groups()

        try:
            extensions.find(b('mq'))
        except KeyError:
            return ''

        q = repo.mq

        print(repr(out))
        if out == b('patches') and not os.path.isdir(q.path):
            out = b('')
        elif out.startswith(b('patches-')):
            out = out[8:]

        return _with_groups(g, out) if out else ''

    def _rev(m):
        g = m.groups()

        parents = repo[None].parents()
        parent = 0 if '|merge' not in g else 1
        parent = parent if len(parents) > parent else None

        rev = parents[parent].rev() if parent is not None else -1
        return _with_groups(g, b('%d' % rev)) if rev >= 0 else ''

    def _root(m):
        return _with_groups(m.groups(), repo.root) if repo.root else ''

    def _status(m):
        g = m.groups()

        st = repo.status(unknown=True)
        modified = any((st.modified, st.added, st.removed, st.deleted))
        unknown = len(st.unknown) > 0

        flag = b('')
        if '|modified' not in g and '|unknown' not in g:
            flag = b('!') if modified else b('?') if unknown else ''
        else:
            if '|modified' in g:
                flag += b('!') if modified else b('')
            if '|unknown' in g:
                flag += b('?') if unknown else b('')

        return _with_groups(g, flag) if flag else ''

    def _tags(m):
        # Show tags of p1.
        # As an alternative, we could show tags of p1 and p2.
        g = m.groups()

        sep = b(g[2][1:]) if g[2] else b(' ')
        tags = repo[b('.')].tags()

        quiet = _get_filter('quiet', g)
        if quiet:
            tags = filter(lambda tag: tag != b('tip'), tags)

        return _with_groups(g, sep.join(tags)) if tags else ''

    def _task(m):
        try:
            task = extensions.find(b('tasks')).current(repo)
            return _with_groups(m.groups(), task) if task else ''
        except KeyError:
            return ''

    def _tip(m):
        g = m.groups()

        format = short if '|short' in g else hex

        tip = repo[len(repo) - 1]
        rev = tip.rev()
        tip = format(tip.node()) if '|node' in g else b('%d' % tip.rev())

        return _with_groups(g, tip) if rev >= 0 else ''

    def _update(m):
        current_rev = repo[None].parents()[0]

        # Get the tip of the branch for the current branch
        try:
            heads = repo.branchmap()[current_rev.branch()]
            tip = heads[-1]
        except (KeyError, IndexError):
            # We are in an empty repository.

            return ''

        for head in reversed(heads):
            if not repo[head].closesbranch():
                tip = head
                break

        return _with_groups(m.groups(), b('^')) if repo[tip].node() != current_rev.node() else ''

    if opts.get("angle_brackets"):
        tag_start = r'\<([^><]*?\<)?'
        tag_end = r'(\>[^><]*?)?>'
        brackets = '<>'
    else:
        tag_start = r'\{([^{}]*?\{)?'
        tag_end = r'(\}[^{}]*?)?\}'
        brackets = '{}'

    patterns = {
        'bookmark': _bookmark,
        'branch(\|quiet)?': _branch,
        'closed(\|quiet)?': _closed,
        'count(\|[^%s]*?)?' % brackets[-1]: _count,
        'node(?:'
            '(\|short)'
            '|(\|merge)'
            ')*': _node,
        'patch(?:'
            '(\|topindex)'
            '|(\|applied)'
            '|(\|unapplied)'
            '|(\|count)'
            '|(\|quiet)'
            ')*': _patch,
        'patches(?:' +
            '(\|join\([^%s]*?\))' % brackets[-1] +
            '|(\|reverse)' +
            '|(\|hide_applied)' +
            '|(\|hide_unapplied)' +
            '|(\|pre_applied\([^%s]*?\))' % brackets[-1] +
            '|(\|post_applied\([^%s]*?\))' % brackets[-1] +
            '|(\|pre_unapplied\([^%s]*?\))' % brackets[-1] +
            '|(\|post_unapplied\([^%s]*?\))' % brackets[-1] +
            ')*': _patches,
        'queue': _queue,
        'rev(\|merge)?': _rev,
        'root': _root,
        'root\|basename': _basename,
        'status(?:'
            '(\|modified)'
            '|(\|unknown)'
            ')*': _status,
        'tags(?:' +
            '(\|quiet)' +
            '|(\|[^%s]*?)' % brackets[-1] +
            ')*': _tags,
        'task': _task,
        'tip(?:'
            '(\|node)'
            '|(\|short)'
            ')*': _tip,
        'update': _update
    }

    if not fs:
        fs = repo.ui.config(b"prompt", b"template", b"")

    fs = s(fs)
    for tag, repl in patterns.items():
        fs = re.sub(tag_start + tag + tag_end, repl, fs)
    fs = b(fs)

    ui.status(fs)

help.helptable += (
    ([b('prompt-keywords')], b('Keywords supported by hg-prompt'),
     lambda _: b('''hg-prompt currently supports a number of keywords.

Some keywords support filters.  Filters can be chained when it makes
sense to do so.  When in doubt, try it!

bookmark
     Display the current bookmark (requires the bookmarks extension).

branch
     Display the current branch.

     |quiet
         Display the current branch only if it is not the default branch.

closed
     Display `X` if working on a closed branch (i.e. committing now would reopen
     the branch).

count
     Display the number of revisions in the given revset (the revset `all()`
     will be used if none is given).

     See `hg help revsets` for more information.

     |REVSET
         The revset to count.

node
     Display the (full) changeset hash of the current parent.

     |short
         Display the hash as the short, 12-character form.

     |merge
         Display the hash of the changeset you're merging with.

patch
     Display the topmost currently-applied patch (requires the mq
     extension).

     |count
         Display the number of patches in the queue.

     |topindex
         Display (zero-based) index of the topmost applied patch in the series
         list (as displayed by :hg:`qtop -v`), or the empty string if no patch
         is applied.

     |applied
         Display the number of currently applied patches in the queue.

     |unapplied
         Display the number of currently unapplied patches in the queue.

     |quiet
         Display a number only if there are any patches in the queue.

patches
     Display a list of the current patches in the queue.  It will look like
     this:

         :::console
         $ hg prompt '{patches}'
         bottom-patch -> middle-patch -> top-patch

     |reverse
         Display the patches in reverse order (i.e. topmost first).

     |hide_applied
         Do not display applied patches.

     |hide_unapplied
         Do not display unapplied patches.

     |join(SEP)
         Display SEP between each patch, instead of the default ` -> `.

     |pre_applied(STRING)
         Display STRING immediately before each applied patch.  Useful for
         adding color codes.

     |post_applied(STRING)
         Display STRING immediately after each applied patch.  Useful for
         resetting color codes.

     |pre_unapplied(STRING)
         Display STRING immediately before each unapplied patch.  Useful for
         adding color codes.

     |post_unapplied(STRING)
         Display STRING immediately after each unapplied patch.  Useful for
         resetting color codes.

queue
     Display the name of the current MQ queue.

rev
     Display the repository-local changeset number of the current parent.

     |merge
         Display the repository-local changeset number of the changeset you're
         merging with.

root
     Display the full path to the root of the current repository, without a
     trailing slash.

     |basename
         Display the directory name of the root of the current repository. For
         example, if the repository is in `/home/u/myrepo` then this keyword
         would expand to `myrepo`.

status
     Display `!` if the repository has any changed/added/removed files,
     otherwise `?` if it has any untracked (but not ignored) files, otherwise
     nothing.

     |modified
         Display `!` if the current repository contains files that have been
         modified, added, removed, or deleted, otherwise nothing.

     |unknown
         Display `?` if the current repository contains untracked files,
         otherwise nothing.

tags
     Display the tags of the current parent, separated by a space.

     |quiet
         Display the tags of the current parent, excluding the tag "tip".

     |SEP
         Display the tags of the current parent, separated by `SEP`.

task
     Display the current task (requires the tasks extension).

tip
     Display the repository-local changeset number of the current tip.

     |node
         Display the (full) changeset hash of the current tip.

     |short
         Display a short form of the changeset hash of the current tip (must be
         used with the **|node** filter)

update
     Display `^` if the current parent is not the tip of the current branch,
     otherwise nothing.  In effect, this lets you see if running `hg update`
     would do something.
''')),
)
