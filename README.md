requirements.txt
================

Plugin for Sublime Text 2/3 providing autocompletion, syntax highlight and easy version management in requirements.txt files.

Installation
============

Install using Package Control or clone this repository into `Packages/requirementstxt` folder (WARNING: previously we used a dot in the package name here, but SublimeText3 changed the way it imports packages, and we need to fall back to ascii name)

Usage
=====

- Open any requirements.txt file or Set syntax: requirements.txt of newly created file.
- Start typing package name -> autocompletion should trigger automatically.
- When cursor is placed on a single line, press `Alt+,` to pin package to the most recent version but still in the current major line. For example, if the current version of xyz is 1.2.3, requirements.txt will generate following version line: xyz>=1.2.3,<2.0.0 following http://semver.org/.
- If you wish to hard pin most recent versions, use `Alt+Shift+,` -> line will be replaced with xyz==1.2.3
- If you wish to pin a specific version, press `Alt+.` (soft) or `Alt+Shift+.` (hard) and pick a version from a quick panel.
- Commands with `,` support mutliline and multicursor selections. If you wish to bring requirements.txt file up to date, just `Ctrl+A` & `Alt+Shift+`.
- Using requirements.txt also normalizes package names, so mysql-python becomes MySQL-python.


Screenshots
===========

* ![](./doc/img/autocomplete.png) Autocomplete
* ![](./doc/img/completed.png) Completed
* ![](./doc/img/soft_ver_sel.png) Select exact version for soft pin `Alt+.`
* ![](./doc/img/hard_ver_sel.png) Select exact version for hard pin `Alt+Shift+.`
* ![](./doc/img/soft_pin.png) Automatically soft pin most recent version `Alt+,`
* ![](./doc/img/hard_pin.png) Automatically hard pin most recent version `Alt+Shift+,`
* ![](./doc/img/selection.png) Multi-line selection
* ![](./doc/img/selection_soft.png) Multi-line selection & `Alt+,`
* ![](./doc/img/multicursor.png) Multiple cursors
* ![](./doc/img/multicursor_hard.png) Multiple cursor & `Alt+Shift+,`
