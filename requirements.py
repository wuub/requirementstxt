#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement, division, absolute_import

import re
import os
import os.path
import time
import threading
import sublime
import sublime_plugin

try:
    from xmlrpclib import ServerProxy
    import ConfigParser as configparser
    unicode_type = unicode
except ImportError:
    from xmlrpc.client import ServerProxy
    import configparser
    unicode_type = str


def get_pip_index():
    """return url of pypi xmlrpc endpoint"""
    pip_index = "http://pypi.python.org/pypi"  # xmlrpc
    pip_index = os.environ.get("PIP_INDEX", pip_index)
    try:
        parser = configparser.SafeConfigParser()
        parser.read(os.path.expanduser("~/.pip/pip.conf"))
        pip_index = parser.get("global", "index")
    except configparser.Error:
        pass  # just ignore
    settings = sublime.load_settings('requirementstxt.sublime-settings')
    pip_index = settings.get("pip_index", pip_index)
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


class FakePackagesIndex(object):
    def __init__(self, url): 
        self._url = url

    def list_packages(self):
        time.sleep(3.0)
        return ["Flask", "Flask-SqlAlchemy", "Flask-WTF"]

    def package_releases(self, package_name):
        time.sleep(1.0)
        return ["1.1.1", "1.1.2"]


def plugin_loaded():
    """Monkeypatch ServerProxy for testing on plugin load"""
    if sublime.load_settings('requirementstxt.sublime-settings').get("debug", False):
        global ServerProxy
        ServerProxy = FakePackagesIndex

CACHE = SimpleCache()


def _fetch_packages():
    """Does the actual package list fetch, returns a list of unicode names"""
    sublime.status_message("requirements.txt: listing packages...")
    packages = ServerProxy(get_pip_index()).list_packages()
    sublime.status_message("requirements.txt: got {}".format(len(packages)))
    if not isinstance(packages[0], unicode_type):
        packages = [pkg.decode("utf-8") for pkg in packages]
    CACHE.set("--packages--", packages, ttl=5 * 60)


def list_packages():
    cached = CACHE.get("--packages--", None)
    if cached is not None:
        return cached
    CACHE.set("--packages--", [], ttl=30)
    threading.Thread(target=_fetch_packages).start()
    return []


def releases(package_name):
    """Return sorted list of releases for given package name"""
    cached = CACHE.get(package_name)
    if cached:
        return cached
    pypi = ServerProxy(get_pip_index())
    rels = pypi.package_releases(package_name)
    sorted_releases = sorted(rels, key=lambda a: tuple(_parse_version_parts(a)))
    CACHE.set(package_name, sorted_releases, ttl=2 * 60)
    return sorted_releases


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


def requirements_file(view):
    fname = view.file_name()
    if not fname:
        return False
    basename = os.path.basename(fname)
    return basename == "requirements.txt"


def requirements_view(view):
    return "source.requirementstxt" in view.scope_name(view.sel()[0].begin())


class RequirementsClearCache(sublime_plugin.WindowCommand):
    def run(self):
        CACHE.clear()
        sublime.status_message("requirements.txt: cache cleared")


class RequirementsAutoVersion(sublime_plugin.TextCommand):
    def run(self, edit, strict=False):
        if not requirements_view(self.view):
            return True

        packages = list_packages()
        pkg_dict = dict(((name.lower(), name) for name in packages))

        for line_sel, line in self.selected_lines():
            lower_pkg_name = self.package_name(line).lower()
            if lower_pkg_name not in pkg_dict:
                continue
            real_name = pkg_dict[lower_pkg_name]
            sorted_releases = releases(real_name)

            most_recent = sorted_releases[-1]
            if strict:
                version_string = self.strict_version(most_recent)
            else:
                version_string = self.non_strict_version(most_recent)

            self.view.replace(edit, line_sel, real_name + version_string)

    def strict_version(self, most_recent):
        return "==" + most_recent

    def non_strict_version(self, most_recent):
        next_major = str(int(most_recent.split(".", 1)[0]) + 1)
        next_version = ".".join([next_major] + ["0" for x in most_recent.split(".")[1:]])
        return ">=%s,<%s" % (most_recent, next_version)

    def package_name(self, line):
        match = re.match("(.*?)[<=>].*", line)
        if not match:
            return line
        return match.group(1).strip()

    def selected_lines(self):
        v = self.view
        v.run_command("split_selection_into_lines")
        for sel in v.sel():
            for line in v.lines(sel):
                yield line, v.substr(line)


class RequirementsEventListener(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if not requirements_view(view):
            return True
        packages = list_packages()
        lower_prefix = prefix.lower()

        completions = [(pkg, pkg) for pkg in packages if pkg.lower().startswith(lower_prefix)]
        return completions, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

    def on_load(self, view):
        if not requirements_file(view):
            return
        syntax_file = "Packages/requirements.txt/requirementstxt.tmLanguage"
        if hasattr(sublime, "find_resources"):
            syntax_file = sublime.find_resources("requirementstxt.tmLanguage")[0]
        view.set_syntax_file(syntax_file)
