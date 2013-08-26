#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement, division, absolute_import

import re
import os
import os.path
import time
import functools
import threading
import sublime
import sublime_plugin

try:
    import ConfigParser as configparser
    from urllib2 import Request, urlopen
    unicode_type = unicode
    PY2 = True
except ImportError:
    import configparser
    from urllib.request import Request, urlopen
    unicode_type = str
    PY2 = False

CACHE = None
SETTINGS = None
SETTINGS_PIP_INDEX = None

def plugin_loaded():
    global CACHE, SETTINGS, SETTINGS_PIP_INDEX
    CACHE = SimpleCache()

    ## meh, get around st2 + osx threading problems
    SETTINGS = sublime.load_settings('requirementstxt.sublime-settings')
    SETTINGS_PIP_INDEX = SETTINGS.get("pip_index", None)

    def update_global():
        global SETTINGS_PIP_INDEX
        SETTINGS_PIP_INDEX = SETTINGS.get("pip_index", None)
    SETTINGS.add_on_change("pip_index", update_global)


def get_pip_index():
    """return url of pypi xmlrpc endpoint"""
    if PY2 and sublime.platform() == "osx":
        ## DON'T EVEN THINK about changing this back to http
        ## somehow http transport is broken on py2.6.7/osx
        pip_index = "https://pypi.python.org/pypi"  # xmlrpc
    else:
        ## AND GUESS WHAT happens on other configurations if you try to use https?
        ## NotImplementedError: your version of http.client doesn't support HTTPS
        ## AAAARRRGGHHHHSHSHSHSSSS someone should be paying me good money for
        ## this stuff
        pip_index = "http://pypi.python.org/pypi"  # xmlrpc

    pip_index = os.environ.get("PIP_INDEX", pip_index)
    try:
        parser = configparser.SafeConfigParser()
        parser.read(os.path.expanduser("~/.pip/pip.conf"))
        pip_index = parser.get("global", "index")
    except configparser.Error:
        pass  # just ignore

    pip_index = SETTINGS_PIP_INDEX or pip_index
    return pip_index


class SimpleCache(object):
    """Dumb cache with TTL"""

    def __init__(self):
        self._dict = {}

    def set(self, key, value, ttl=60):
        self._dict[key] = (value, time.time() + ttl)

    def get(self, key, default=None):
        (value, expire) = self._dict.get(key, (None, 0))
        if expire < time.time():
            return default
        return value

    def clear(self):
        self._dict.clear()


def status_message(msg):
    """Workaround for osx run_on_main_thread problem"""
    sublime.set_timeout(functools.partial(sublime.status_message, msg), 0)


def _fetch_packages():
    """Does the actual package list fetch, returns a list of unicode names"""
    status_message("requirements.txt: listing packages...")
    query = b'''<?xml version='1.0'?>\n<methodCall>\n<methodName>list_packages</methodName>\n<params></params>\n</methodCall>\n'''
    req = Request(get_pip_index(), data=query, headers={"Content-Type": "text/xml"})
    result = urlopen(req).read().decode("utf-8")
    if "<fault>" in result:
        packages = []
    else:
        packages = re.findall("<string>(.+?)</string>", result)
    status_message("requirements.txt: got {count}".format(count=len(packages)))
    if not isinstance(packages[0], unicode_type):
        packages = [pkg.decode("utf-8") for pkg in packages]

    pkg_dict = dict(((name.lower(), name) for name in packages))
    CACHE.set("--packages--", pkg_dict, ttl=5 * 60)


def list_packages():
    """Return a DICT of lowercase_name -> CaseSensitive_Name of packages
       available on get_pip_index() server"""
    cached = CACHE.get("--packages--", None)
    if cached is not None:
        return cached
    # thread has 30 seconds to get packages, otherwise cache will
    # timeout and next thread will be spawned
    CACHE.set("--packages--", {}, ttl=30)
    threading.Thread(target=_fetch_packages).start()
    return {}


## Yanked from pkg_resources
component_re = re.compile(r'(\d+ | [a-z]+ | \.| -)', re.VERBOSE)
replace = {
    'pre': 'c',
    'preview': 'c',
    '-': 'final-',
    'rc': 'c',
    'dev': '@'
}

def _parse_version_parts(s):
    for part in component_re.split(s):
        part = replace.get(part, part)
        if part in ['', '.']:
            continue
        if part[:1] in '0123456789':
            yield part.zfill(8)    # pad for numeric comparison
        else:
            yield '*' + part
    yield '*final'  # ensure that alpha/beta/candidate are before final


def _releases(name, show_hidden=False):
    """Because ServerProxy().package_releases() is soooo f*$& broken
       under different ST2/3 + osx/windows/linux configurations"""
    template = '''<?xml version='1.0'?>\n<methodCall>\n<methodName>package_releases</methodName>\n<params>\n<param>\n<value><string>{name}</string></value>\n</param>\n<param>\n<value><boolean>{flag}</boolean></value>\n</param>\n</params>\n</methodCall>\n'''
    flag = 1 if show_hidden else 0
    payload = template.format(name=name, flag=flag).encode("utf-8")
    req = Request(get_pip_index(), data=payload, headers={"Content-Type": "text/xml"})
    result = urlopen(req).read().decode("utf-8")
    if "<fault>" in result:
        return []
    matches = re.findall("<string>(.+?)</string>", result)
    return matches


def releases(name, show_hidden=False):
    """Return sorted list of releases for given package name
       If show_hidden is set to true, returns all packages
    """
    key = "{name}-{hidden}".format(name=name, hidden=show_hidden)
    cached = CACHE.get(key)
    if cached:
        return cached
    rels = _releases(name, show_hidden)
    sorted_releases = sorted(rels, key=lambda a: tuple(_parse_version_parts(a)))
    CACHE.set(key, sorted_releases, ttl=2 * 60)
    return sorted_releases


def requirements_file(view):
    """Return true if given view should be treated as requirements.txt file"""
    fname = view.file_name()
    if not fname:
        return False
    basename = os.path.basename(fname)
    if basename == "requirements.txt":
        return True
    dirname = os.path.basename(os.path.dirname(fname))
    if dirname == "requirements" and fname.endswith(".txt"):
        return True
    return False


def requirements_view(view):
    return "source.requirementstxt" in view.scope_name(view.sel()[0].begin())


def package_name(line):
    """Parse requirements.txt line and return package name
       possibly with extras"""
    match = re.match("(.*?)[<=>].*", line)
    if not match:
        return line
    return match.group(1).strip()


def normalized_name(package_line):
    """Reurn lowercase package name and extras (unchanged) or None"""
    lower = package_line.lower()
    extras_match = re.search(r'\[(.*)\]', package_line)
    extras = extras_match.group(1) if extras_match else None
    return re.sub(r'\[.*\]', "", lower), extras


def strict_version(version):
    """Return a hard pinned version string"""
    return "==" + version


def non_strict_version(version):
    """Where possible, return soft pinned pip version text,
       while still keeping package in the current major release line.
       If semver parsing fails for any reason, returns soft pinned
       version without upper limit"""
    try:
        next_major = str(int(version.split(".", 1)[0]) + 1)
        next_version = ".".join([next_major] + ["0" for _ in version.split(".")[1:]])
    except:
        return ">=%s" % (version,)  # pytz ;-(
    else:
        return ">=%s,<%s" % (version, next_version)


def selected_lines(view):
    """Iterate over selected lines in given view"""
    view.run_command("split_selection_into_lines")
    for sel in view.sel():
        for line in view.lines(sel):
            yield line, view.substr(line)


class RequirementsClearCache(sublime_plugin.WindowCommand):
    """Forced pypi cache clear"""
    def run(self):
        CACHE.clear()
        sublime.status_message("requirements.txt: cache cleared")


class RequirementsAutoVersion(sublime_plugin.TextCommand):
    def run(self, edit, strict=False):
        if not requirements_view(self.view):
            return True

        pkg_dict = list_packages()

        for line_sel, line in selected_lines(self.view):
            lower_pkg_name, extras = normalized_name(package_name(line))
            if lower_pkg_name not in pkg_dict:
                continue
            real_name = pkg_dict[lower_pkg_name]
            sorted_releases = releases(real_name)
            if extras:
                full_name = "{name}[{extras}]".format(name=real_name, extras=extras)
            else:
                full_name = real_name

            version = sorted_releases[-1]
            if strict:
                version_string = strict_version(version)
            else:
                version_string = non_strict_version(version)

            self.view.replace(edit, line_sel, full_name + version_string)


class RequirementsReplaceLine(sublime_plugin.TextCommand):
    def run(self, edit, line_value):
        # damn you ST3 ;)
        self.view.replace(edit, self.view.line(self.view.sel()[0]), line_value)


class RequirementsPromptVersion(sublime_plugin.TextCommand):
    def run(self, edit, strict=False):
        if not requirements_view(self.view):
            return True

        line_sel, line = next(selected_lines(self.view), (None, None))
        if not line:
            # either no selection or empty line
            return

        pkg_dict = list_packages()
        lower_pkg_name, extras = normalized_name(package_name(line))
        if lower_pkg_name not in pkg_dict:
            return
        real_name = pkg_dict[lower_pkg_name]
        versions = list(reversed(releases(real_name, True)))

        full_name = real_name
        if extras:
            full_name += "[{extras}]".format(extras=extras)

        ver_func = strict_version if strict else non_strict_version
        choices = [full_name + ver_func(version) for version in versions]

        callback = functools.partial(self.on_done, choices)
        self.view.window().show_quick_panel(choices, callback, 0, 0)

    def on_done(self, choices, picked):
        if picked == -1:
            return
        self.view.run_command("requirements_replace_line", {
            "line_value": choices[picked]
        })


class RequirementsEventListener(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if not requirements_view(view):
            return True
        pkg_dict = list_packages()
        lower_prefix = prefix.lower()

        completions = [(pkg, pkg) for lower_name, pkg in pkg_dict.items() if lower_name.startswith(lower_prefix)]
        return completions, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

    def on_load(self, view):
        if not requirements_file(view):
            return
        syntax_file = "Packages/requirementstxt/requirementstxt.tmLanguage"
        if hasattr(sublime, "find_resources"):
            syntax_file = sublime.find_resources("requirementstxt.tmLanguage")[0]
        view.set_syntax_file(syntax_file)


if PY2:
    plugin_loaded()

