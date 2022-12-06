# -*- coding: utf-8 -*-
from __future__ import (unicode_literals)
##########################################################
# Author: Yichen Huang (Eugene)
# GitHub: https://github.com/yichen0831/opencc-python
# January, 2016
##########################################################

##########################################################
# Revised by: Hopkins 
# June, 2016
# Apache License Version 2.0, January 2004
# - Use a tree-like structure hold the result during conversion
# - Always choose the longest matching string from left to right in dictionary
#   by trying lookups in the dictionary rather than looping
# - Split the incoming string into smaller strings before processing to improve speed
# - Only match once per dictionary
# - If a dictionary is configured as part of a group, only match once per group
#   in order of the listed dictionaries
# - Cache the results of reading a dictionary in self.dict_cache
# - Use "from __future__ import" to allow support for both Python 2.7
#   and Python >3.2
##########################################################

import io
import os
import json
import re

CONFIG_FILE = 'config'
DICT_FILE = 'dictionary'

# Dictionary mapping ("old", "new") as a key and conversion count as a value
_counts_dict = {}

class OpenCC:
    def __init__(self, resource_getter, conversion=None):
        """
        init OpenCC
        :param resource_getter: function that takes 2 parameters.
         The first parameter is CONFIG_FILE, or DICT_FILE
         The second parameter is a file name associated with the directory.
         It returns bytes from the selected file.
        :param conversion: the conversion of usage, options are
         'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', and 'tw2sp'
         check the json file names in config directory
        :return: None
        """
        _counts_dict.clear()
        self.conversion_name = ''
        self.conversion = conversion
        self._dict_init_done = False
        self._dict_chain = list()
        self._dict_chain_data = list()
        self.dict_cache = dict()
        self.resource_getter = resource_getter
        # List of sentence separators from OpenCC PhraseExtract.cpp. None of these separators are allowed as
        # part of a dictionary entry
        self.split_chars_re = re.compile(
            r'(\s+|-|,|\.|\?|!|\*|　|，|。|、|；|：|？|！|…|“|”|‘|’|『|』|「|」|﹁|﹂|—|－|（|）|《|》|〈|〉|～|．|／|＼|︒|︑|︔|︓|︿|﹀|︹|︺|︙|︐|［|﹇|］|﹈|︕|︖|︰|︳|︴|︽|︾|︵|︶|｛|︷|｝|︸|﹃|﹄|【|︻|】|︼|—|， |： |︲|～)')
        if self.conversion is not None:
            self._init_dict()

##    def clear_counts (self):
##        _counts_dict.clear()
##
##    def get_counts (self):
##        return _counts_dict

    def convert(self, string):
        """
        Convert string from Simplified Chinese to Traditional Chinese or vice versa
        """

        # echo the input if no conversion is wanted
        if self.conversion == "no_conversion":
            return string

        if not self._dict_init_done:
            self._init_dict()
            self._dict_init_done = True

        result = []
        # Separate string using the list of separators in a regular expression
        split_string_list = self.split_chars_re.split(string)
        for i in range(0, len(split_string_list)):
            if i % 2 == 0:
                # Work with the text string
                # Append converted string to result
                result.append(self._convert(split_string_list[i], self._dict_chain_data))
            else:
                # Work with the separator
                # Append separator string to converted_string
                result.append(split_string_list[i])
        # Join it all together to return a result
        return "".join(result)

    def _convert(self, string, dictionary = [], is_dict_group = False):
        """
        Convert string from Simplified Chinese to Traditional Chinese or vice versa
        If a dictionary is part of a group of dictionaries, stop conversion on a word
        after the first match is found.
        :param string: the input string
        :param dictionary: list of dictionaries to be applied against the string
        :param is_dict_group: indicates if this is a group of dictionaries in which only
                              the first match in the dict group should be used
        :return: converted string
        """
        tree = StringTree(string)
        for c_dict in dictionary:
            if isinstance(c_dict, tuple):
                tree.convert_tree(c_dict)
                if not is_dict_group:
                    # Don't reform the string here if the dictionary list is part of a group
                    # Recreate the tree for next loop iteration
                    tree = StringTree("".join(tree.inorder()))
            else:
                # This is a list of dictionaries. Call back in with the dictionary
                # list but specify that this is a group
                tree = StringTree(self._convert("".join(tree.inorder()), c_dict, True))
        return "".join(tree.inorder())

    def _init_dict(self):
        """
        initialize the dict with chosen conversion
        :return: None
        """
        if self.conversion is None:
            raise ValueError('conversion is not set')

        self._dict_chain = []
##        print(self.conversion)
        config = self.conversion + '.json'
##        print(config)
        bytes = self.resource_getter(CONFIG_FILE, config)
        if bytes is not None:
            setting_json = json.loads(bytes.decode("utf-8"))
        else:
            raise IOError('unable to open opencc config file')

        self.conversion_name = setting_json.get('name')

        for chain in setting_json.get('conversion_chain'):
            self._add_dict_chain(self._dict_chain, chain.get('dict'))

        self._dict_chain_data = []
        self._add_dictionaries(self._dict_chain, self._dict_chain_data)
        self._dict_init_done = True

    def _add_dictionaries(self, chain_list, chain_data):
        for item in chain_list:
            if isinstance(item, list):
                chain = []
                self._add_dictionaries(item, chain)
                chain_data.append(chain)
            else:
                if not item in self.dict_cache:
                    map_dict = {}
                    max_len = 1
                    bytes = self.resource_getter(DICT_FILE, item)
                    if bytes is not None:
                        converted_data = bytes.decode("utf-8")
                        converted_data_list = converted_data.splitlines()
                        for line in converted_data_list:
                            key, value = line.strip().split('\t')
                            map_dict[key] = value
                            if len(key) > max_len:
                                max_len = len(key)
                        chain_data.append((max_len, map_dict))
                        self.dict_cache[item] = (max_len, map_dict)
                    else:
                        #Raise exception
                        raise IOError('unable to open opencc dictionary')
                else:
                    #Use the cached version
                    chain_data.append(self.dict_cache[item])

    def _add_dict_chain(self, dict_chain, dict_dict):
        """
        add dict chain
        :param dict_chain: the dict chain to add to
        :param dict_dict: the dict to be added in
        :return: None
        """
        if dict_dict.get('type') == 'group':
            # Create a sublist of dictionaries for a group
            chain = []
            for dict_item in dict_dict.get('dicts'):
                self._add_dict_chain(chain, dict_item)
            dict_chain.append(chain)
        elif dict_dict.get('type') == 'txt':
            filename = dict_dict.get('file')
            dict_file = filename
            dict_chain.append(dict_file)

    def set_conversion(self, conversion):
        """
        set conversion
        :param conversion: the conversion of usage, options are
         'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', and 'tw2sp'
         check the json file names in config directory
        :return: None
        """
        if self.conversion == conversion:
            return
        elif conversion == "no_conversion":
            # just loopback the input
            self.conversion = conversion
        else:
            self._dict_init_done = False
            self.conversion = conversion


class StringTree:
    """
    Class to hold string during modification process.
    """
    def __init__(self, string):
        self.string = string
        self.old_string = string
        self.left = None
        self.right = None
        self.string_len = len(string)
        self.matched = False

    def convert_tree(self, test_dict):
        """
        Compare smaller and smaller sub-strings going from left to
        right against test_dict. If an entry is found, place the remaining
        string portion on the left and right into sub-trees and recurively
        convert each.
        :param test_dict: a tuple of the max key length and dict currently being
                          applied against the string
        :return: None
        """
        if self.matched == True:
            if self.left is not None:
                self.left.convert_tree(test_dict)
            if self.right is not None:
                self.right.convert_tree(test_dict)
        else:
            test_len = min(self.string_len, test_dict[0])
            while test_len != 0:
                # Loop through trying successively smaller substrings in the dictionary
                for i in range(0, self.string_len - test_len + 1):
                    if self.string[i:i+test_len] in test_dict[1]:
                        # Match found.
                        if i > 0:
                            # Put everything to the left of the match into the left sub-tree and further process it
                            self.left = StringTree(self.string[:i])
                            self.left.convert_tree(test_dict)
                        if (i+test_len) < self.string_len:
                            # Put everything to the right of the match into the right sub-tree and further process it
                            self.right = StringTree(self.string[i+test_len:])
                            self.right.convert_tree(test_dict)
                        # Save the dictionary value in this tree
                        value = test_dict[1][self.string[i:i+test_len]]
                        self.old_string = self.string[i:i+test_len]
                        if len(value.split(' ')) > 1:
                            # multiple mapping, use the first one for now
                            value = value.split(' ')[0]
                        self.string = value
                        self.string_len = len(self.string)
                        self.matched = True
                        return
                test_len -= 1

    def inorder(self):
        """
        Inorder traversal of this tree
        :param None
        :return: list of words from a inorder traversal of the tree
        """
        result = []

        if self.left is not None:
            result += self.left.inorder()

        result.append(self.string)

        if self.right is not None:
            result += self.right.inorder()
        return result

