import os
import sys
import yaml
import plistlib


def translate_yaml(in_fname, out_fname):

    print("Traslating %s -> %s" % (in_fname, out_fname))
    with open(in_fname) as j:
        data = yaml.load(j)
    with open(out_fname, "w") as t:
        plistlib.writePlist(data, t)


def main():
    path = os.path.dirname(sys.argv[0]) or os.curdir

    if len(sys.argv) == 2:
        oneopen = os.path.normpath(sys.argv[1])
        parts = os.path.splitext(oneopen)
        if parts[1] == ".yaml":
            translate_yaml(oneopen, parts[0])
            return

    for fname in os.listdir(path):
        names = os.path.splitext(fname)
        if names[-1] != ".yaml":
            continue
        in_fname = os.path.join(path, fname)
        out_fname = os.path.join(path, names[0])
        translate_yaml(in_fname, out_fname)


if __name__ == "__main__":
    main()
