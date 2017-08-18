from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
"""
----------------------------
NOTE:
The "tokenize" function given below was taken from the file
"smartypants.py" which was part of the Calibre plugin
"diaps_toolbag"
----------------------------

----------------------------
SmartyPants ported to Python
----------------------------

Ported by `Chad Miller`_
Copyright (c) 2004, 2007 Chad Miller

original `SmartyPants`_ by `John Gruber`_
Copyright (c) 2003 John Gruber
"""

import re

def tokenize(str):
    """
    Parameter:  String containing HTML markup.
    Returns:    Reference to an array of the tokens comprising the input
                string. Each token is either a tag (possibly with nested,
                tags contained therein, such as <a href="<MTFoo>">, or a
                run of text between tags. Each element of the array is a
                two-element array; the first is either 'tag' or 'text';
                the second is the actual value.

    Based on the _tokenize() subroutine from Brad Choate's MTRegex plugin.
        <http://www.bradchoate.com/past/mtregex.php>
    """

    tokens = []

    # depth = 6
    # nested_tags = "|".join(['(?:<(?:[^<>]',] * depth) + (')*>)' * depth)
    # match = r"""(?: <! ( -- .*? -- \s* )+ > ) |  # comments
    # (?: <\? .*? \?> ) |  # directives
    # %s  # nested tags       """ % (nested_tags,)
    # tag_soup = re.compile(r"""([^<]*)(<[^>]*>)""")
    tag_soup = re.compile(r"""([^<]*)(<!--.*?--\s*>|<[^>]*>)""", re.S)

    token_match = tag_soup.search(str)

    previous_end = 0
    while token_match is not None:
        if token_match.group(1):
            tokens.append(['text', token_match.group(1)])

        tag = token_match.group(2)
        type_ = 'tag'
        if tag.startswith('<!--'):
            # remove --[white space]> from the end of tag
            if '--' in tag[4:].rstrip('>').rstrip().rstrip('-'):
                type_ = 'text'
        tokens.append([type_, tag])

        previous_end = token_match.end()
        token_match = tag_soup.search(str, token_match.end())

    if previous_end < len(str):
        tokens.append(['text', str[previous_end:]])

    return tokens
