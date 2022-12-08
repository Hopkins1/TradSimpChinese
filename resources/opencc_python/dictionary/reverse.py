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

REV_INPUTS = [
    'JPVariants',
    'TWVariants',
    'TWPhrases',
    'HKVariants'
]


def reverse(rev_inputs=REV_INPUTS):
    """
    reverse the key, value in dictionary file
    :param rev_inputs: the files to be reversed
    :return: None
    """
    dirname = os.path.dirname(__file__)

    for in_file in rev_inputs:
        reversed_dict = {}
        input_file = in_file + '.txt'
        output_file = in_file + 'Rev.txt'
        input_file = os.path.join(dirname, DICT_DIRECTORY, input_file)
        output_file = os.path.join(dirname, DICT_DIRECTORY, output_file)
        with io.open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                split = line.split('\t')
                if len(split) < 2:
                    continue
                term1 = split[0]
                term2 = split[1]

                for char in term2.split(' '):
                    if char in reversed_dict:
                        reversed_dict[char].append(term1)
                    else:
                        reversed_dict[char] = [term1]
        with io.open(output_file, 'w', encoding='utf-8') as f:
            for key in reversed_dict:
                line = key + '\t' + ' '.join(reversed_dict[key]) + '\n'
                f.write(line)


if __name__ == '__main__':
    reverse()
