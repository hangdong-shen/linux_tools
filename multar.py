#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os

def main():
    logs_path="./logs"
    os.chdir(logs_path)
    for file in glob.glob("*.bz2"):
        cmd="tar -xvf %s >/dev/null" %file
        os.system(cmd)

if __name__ == "__main__":
    main()
