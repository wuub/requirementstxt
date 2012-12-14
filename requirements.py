#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement, division, absolute_import

import re
import os
import os.path
import time
import xmlrpclib
import sublime
import sublime_plugin
import ConfigParser


PIP_INDEX = "http://pypi.python.org/pypi"  # xmlrpc
PIP_INDEX = os.environ.get("PIP_INDEX", PIP_INDEX)
try:
    cp = ConfigParser.SafeConfigParser()
    cp.read(os.path.expanduser("~/.pip/pip.conf"))
    PIP_INDEX = cp.get("global", "index")
except ConfigParser.Error:
    pass  # just ignore
settings = sublime.load_settings('requirementstxt.sublime-settings')
PIP_INDEX = settings.get("pip_index", PIP_INDEX)


class SimpleCache(object):
    def __init__(self):
        self._dict = {}

    def set(self, key, value, ttl=60):
        self._dict[key] = (value, time.time() + ttl)

    def get(self, key, default=None):
        (value, expire) = self._dict.get(key, (None, 0))
        if expire < time.time():
            return default
        return value

cache = SimpleCache()


def list_packages():
    cached = cache.get("--packages--", None)
    if cached:
        return cached
    packages = xmlrpclib.ServerProxy(PIP_INDEX).list_packages()
    if not isinstance(packages[0], unicode):
        packages = [pkg.decode("utf-8") for pkg in packages]
    cache.set("--packages--", packages, ttl=5 * 60)
    return packages


def releases(package_name):
    cached = cache.get(package_name)
    if cached:
        return cached
    pypi = xmlrpclib.ServerProxy(PIP_INDEX)
    rels = pypi.package_releases(package_name)
    sorted_releases = sorted(rels, cmp=lambda a, b: cmp(tuple(_parse_version_parts(a)), tuple(_parse_version_parts(b))))
    cache.set(package_name, sorted_releases, ttl=2 * 60)
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


def requirements_view(view):
    fname = view.file_name()
    if not fname:
        return False
    basename = os.path.basename(fname)
    return basename == "requirements.txt"


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
        next_version = ".".join([next_major] + map(lambda x: "0", most_recent.split(".")[1:]))
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
        if not requirements_view(view):
            return
        view.set_syntax_file("Packages/requirements.txt/requirementstxt.tmLanguage")

