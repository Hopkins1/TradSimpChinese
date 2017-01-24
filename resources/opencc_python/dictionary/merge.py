#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

##########################################################
# Author: Yichen Huang (Eugene)
# GitHub: https://github.com/yichen0831/opencc-python
# January, 2016 - Original
# January 2017 - Update to run under Python 2 by Hopkins1
##########################################################

import sys
import os
import io

DICT_DIRECTORY = '.'

MER_INPUTS = [
    'TWPhrasesIT.txt',
    'TWPhrasesName.txt',
    'TWPhrasesOther.txt'
]

MER_OUTPUT = 'TWPhrases.txt'


def merge(mer_inputs=MER_INPUTS, mer_output=MER_OUTPUT):
    """
    merge the phrase files into one file
    :param mer_inputs: the phrase files
    :param mer_output: the output file
    :return: None
    """
    dirname = os.path.dirname(__file__)
    output_file = os.path.join(dirname, DICT_DIRECTORY, mer_output)
    lines = []
    for in_file in MER_INPUTS:
        input_file = os.path.join(dirname, DICT_DIRECTORY, in_file)
        with io.open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                lines.append(line)

    with io.open(output_file, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line)


if __name__ == '__main__':
    merge()
