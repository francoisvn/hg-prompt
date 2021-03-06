Quick Start
===========

This guide will get you up and running so you can put some useful information
into your shell prompt.

If you haven't already [installed][install] it, do that now.

[install]: ../installation/

[TOC]

A Simple (But Useful) Prompt
----------------------------

Edit your `~/.bashrc` file to include something like this:

    hg_ps1() {
        hg prompt "{ on {branch}}{ at {bookmark}}{status}" 2> /dev/null
    }

    export PS1='\u at \h in \w$(hg_ps1)\n$ '

`source ~/.bashrc` after to test it out. Make sure you're in a Mercurial
repository or you won't see anything. This little prompt will give you
something like this:

    steve at myhost in ~/src/hg-prompt on default at feature-bookmark?
    $

An Advanced Prompt
------------------

How about something a little more interesting?

    hg_ps1() {
        hg prompt "{[+{incoming|count}]-->}{root|basename}{/{branch}}{-->[+{outgoing|count}]}{ at {bookmark}}{status}" 2> /dev/null
    }

    export PS1='$(hg_ps1)\n\u at \h in \w\n$ '

And the result (this example assumes one incoming changeset and two outgoing):

    [+1]-->hg-prompt/default-->[+2] at feature-bookmark
    steve at myhost in ~/src/hg-prompt
    $

Learn More
----------

From here you can take a look at the [full documentation][] to see all the
interesting things `hg-prompt` can do.

[full documentation]: ../full-documentation/
