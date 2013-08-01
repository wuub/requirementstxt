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
- When cursor is placed on a single line, press `Alt+,` to pin package to the newest version but still in the current major version. For example, if the current version of xyz is 1.2.3, requirements.txt will generate following version line: xyz>=1.2.3,<2.0.0 following http://semver.org/.
- If you wish to pin exact versions, use `Alt+Shift+,` -> line will be replaced with xyz==1.2.3
- This package supports mutliline and multicursor selections. If you wish to bring requirements.txt file up to date, just `Ctrl+A` & `Alt+Shift+`, it.
- Using requirements.txt also normalizes package names, so mysql-python becomes MySQL-python.


Screenshots
===========

* ![](./doc/img/autocomplete.png) Autocomplete
* ![](./doc/img/completed.png) Completed
* ![](./doc/img/soft_pin.png) Soft pinned `Alt+,`
* ![](./doc/img/hard_pin.png) Hard pinned `Alt+Shift+,`
* ![](./doc/img/selection.png) Multi-line selection
* ![](./doc/img/selection_soft.png) Multi-line selection & `Alt+,`
* ![](./doc/img/multicursor.png) Multiple cursors
* ![](./doc/img/multicursor_hard.png) Multiple cursort & `Alt+Shift+,`
