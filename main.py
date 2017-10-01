# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2016, Hopkins'

import re, os.path
from itertools import tee, islice, izip_longest
from cssutils import  css, stylesheets

try:
    from PyQt5.Qt import Qt, QAction, QDialog, QApplication, QCursor
except:
    from PyQt4.Qt import Qt, QAction, QDialog, QApplication, QCursor

from calibre.gui2.tweak_book.plugin import Tool
from calibre.gui2.tweak_book import editor_name
from calibre.gui2 import error_dialog, info_dialog
from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, get_container
try:
    from calibre.ebooks.oeb.polish.toc import get_toc, find_existing_ncx_toc, commit_toc
except:
    from calibre.ebooks.oeb.polish.toc import get_toc, find_existing_toc, commit_toc
from calibre_plugins.chinese_text.resources.opencc_python.opencc import OpenCC

'''
TradSimpChinese
This Calibre plugin converts the Chinese text characters in an ebook. It can
convert texts using traditional characters in a text containing simplified
characters. It also can convert texts using simplified characters in a text
containing traditional characters.

NOTE:
This code is based on the Calibre plugin Diap's Editing Toolbag

SEE ALSO:
https://en.wikipedia.org/wiki/Simplified_Chinese_characters
https://en.wikipedia.org/wiki/Traditional_Chinese_characters
https://en.wikipedia.org/wiki/Debate_on_traditional_and_simplified_Chinese_characters

'''

# Horizontal full width characters to their vertical presentation forms lookup
_h2v_dict = {'。':'︒', '、':'︑', '；':'︔', '：':'︓', '！':'︕', '？':'︖', '「':'﹁', '」':'﹂', '〈':'︿', '〉':'﹀',
        '『':'﹃', '』':'﹄', '《':'︽', '》':'︾', '【':'︻', '（':'︵', '】':'︼', '）':'︶','〖': '︗', '〗':'︘',
        '〔':'︹', '｛':'︷', '〕':'︺', '｝':'︸', '［':'﹇', '］':'﹈', '…':'︙', '‥':'︰', '—':'︱', '＿':'︳',
        '﹏':'︴', '，':'︐'}
_h2v_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, _h2v_dict.keys())))

# Vertical full width characters to their Horizontal presentation forms lookup
_v2h_dict = {v: k for k, v in _h2v_dict.iteritems()}
_v2h_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, _v2h_dict.keys())))

# The US Kindle Paperwhite does not correctly display some vertical glyph forms. Remove the characters that
# have problems from _h2v_dict
_h2vkindle_dict = {'。':'︒', '：':'︓', '「':'﹁', '」':'﹂', '〈':'︿', '〉':'﹀', '『':'﹃', '』':'﹄', '《':'︽', '》':'︾',
                   '【':'︻', '（':'︵', '】':'︼', '）':'︶', '〔':'︹', '｛':'︷', '〕':'︺',
                   '｝':'︸', '［':'﹇', '］':'﹈', '—':'︱', '﹏':'︴', '，':'︐'}
_h2vkindle_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, _h2vkindle_dict.keys())))

_zh_re = re.compile('lang=\"zh-\w+\"|lang=\"zh\"', re.IGNORECASE)

class TradSimpChinese(Tool):
    from calibre_plugins.chinese_text.resources.opencc_python.opencc import OpenCC
    converter = OpenCC()

    name = 'trad-simp-chinese'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    def create_action(self, for_toolbar=True):
        # Create an action, this will be added to the plugins toolbar and
        # the plugins menu
        ac = QAction(get_icons('images/TradSimpIcon.png'), _('Convert Chinese Text Simplified/Traditional'), self.gui)
        if not for_toolbar:
            # Register a keyboard shortcut for this toolbar action. We only
            # register it for the action created for the menu, not the toolbar,
            # to avoid a double trigger
            self.register_shortcut(ac, 'trad-simp_chinese', default_keys=('Ctrl+Shift+Alt+T',))

        # Pop up a window to ask if the user wants to convert the text
        ac.triggered.connect(self.dispatcher)
        return ac

    def dispatcher(self):
        container = self.current_container  # The book being edited as a container object
        if not container:
            return info_dialog(self.gui, _('No book open'),
                        _('Need to have a book open first.'), show=True)

        self.filesChanged = False
        self.changed_files = []

        from calibre_plugins.chinese_text.dialogs import ConversionDialog
        from calibre_plugins.chinese_text.resources.dialogs import ResultsDialog

        dlg = ConversionDialog(self.gui)
        if dlg.exec_():
            criteria = dlg.getCriteria()
            # Ensure any in progress editing the user is doing is present in the container
            self.boss.commit_all_editors_to_container()
            self.boss.add_savepoint(_('Before: Text Conversion'))

            try:
                conversion = get_configuration(criteria)
                if conversion == 'None':
                    info_dialog(self.gui, _('No Changes'),
                    _('The output configuration selected is not supported.\n Please use a different input/output style combination'), show=True)
                else:
                    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
                    QApplication.processEvents()
                    if conversion != 'no_conversion':
                        self.converter.set_conversion(get_configuration(criteria))
                    self.process_files(criteria)
                    QApplication.restoreOverrideCursor()
            except Exception:
                QApplication.restoreOverrideCursor()
                # Something bad happened report the error to the user
                import traceback
                error_dialog(self.gui, _('Failed'),
                    _('Failed to convert Chinese, click "Show details" for more info'),
                    det_msg=traceback.format_exc(), show=True)
                # Revert to the saved restore point
                self.boss.revert_requested(self.boss.global_undo.previous_container)
            else:
                if self.filesChanged:
                    # Show the user what changes we have made,
                    # allowing then to revert them if necessary
                    accepted = ResultsDialog(self.gui, self.changed_files).exec_()
                    if accepted == QDialog.Accepted:
                        self.boss.show_current_diff()
                    # Update the editor UI to take into account all the changes we
                    # have made
                    self.boss.apply_container_update_to_gui()
                elif conversion != 'None':
                    info_dialog(self.gui, _('No Changes'),
                                _('No text meeting your criteria was found to change.\nNo changes made.'), show=True)

    def process_files(self, criteria):
        container = self.current_container  # The book being edited as a container object
        self.language = 'lang=\"' + get_language_code(criteria) + '\"'
        if criteria[0]:
            # Only convert the selected file
            name = editor_name(self.gui.central.current_editor)
            if not name or container.mime_map[name] not in OEB_DOCS:
                return info_dialog(self.gui, _('Cannot Process'),
                        _('No file open for editing or the current file is not an (x)html file.'), show=True)

            data = container.raw_data(name)
            htmlstr = self.convert_text(data, criteria)
            if htmlstr != data:
                self.filesChanged = True
                self.changed_files.append(name)
                container.open(name, 'wb').write(htmlstr)

        else:
            # Cover the entire book
            # Set metadata and Table of Contents (TOC) if language changed
            if criteria[1] != 0:
                self.filesChanged = set_metadata_toc(container, get_language_code(criteria), criteria, self.changed_files, self.converter)
            # Check for orientation change
            direction_changed = False
            if criteria[7] != 0:
                direction_changed = set_flow_direction(container, get_language_code(criteria), criteria, self.changed_files, self.converter)

            # Cover the text portion
            from calibre_plugins.chinese_text.resources.dialogs import ShowProgressDialog
            d = ShowProgressDialog(self.gui, container, OEB_DOCS, criteria, self.convert_text, _('Converting'))
            cancelled_msg = ''
            if d.wasCanceled():
                cancelled_msg = ' (cancelled)'
            self.filesChanged = self.filesChanged or (not d.clean) or direction_changed
            self.changed_files.extend(d.changed_files)

    def convert_text(self, data, criteria):
        from calibre_plugins.chinese_text.resources.utilities import tokenize

        htmlstr_corrected = replace_quotations(data, criteria)

        tokens = tokenize(htmlstr_corrected)
        result = []
        for cur_token in tokens:
            if cur_token[0] == "tag":
                # change language code inside of tags
                if criteria[0] != 0:
                    result.append(_zh_re.sub(self.language, cur_token[1]))
                else:
                    result.append(cur_token[1])
            else:
                # Update punctuation based on text direction if needed
                if criteria[8] != 0:
                    if criteria[7] == 1:
                        cur_token[1] = multiple_replace(_v2h_dict_regex, _v2h_dict, cur_token[1])
                    elif criteria[7] == 2:
                        if criteria[8] == 1:
                            cur_token[1] = multiple_replace(_h2v_dict_regex, _h2v_dict, cur_token[1])
                        else:
                            cur_token[1] = multiple_replace(_h2vkindle_dict_regex, _h2vkindle_dict, cur_token[1])
                # Convert text if needed
                if criteria[1] != 0:
                    result.append(self.converter.convert(cur_token[1]))
                else:
                    result.append(cur_token[1])
        return "".join(result)


def replace_quotations(data, criteria):
    # Create regular expressions to modify quote styles
    trad_to_simp_quotes = {'「':'＂', '」':'＂', '『':'＇', '』':'＇'}
    trad_to_simp_re = re.compile('|'.join(map(re.escape, trad_to_simp_quotes)))

    trad_to_simp_smart_quotes = {'「':'“', '」':'”', '『':'‘', '』':'’'}
    trad_to_simp_smart_re = re.compile('|'.join(map(re.escape, trad_to_simp_smart_quotes)))

    # Only change double quotes since a lone single quote might be used in an abbreviation
    simp_to_trad_quotes = {'“':'「', '”':'」'}
    simp_to_trad_re = re.compile('|'.join(map(re.escape, simp_to_trad_quotes)))

    # update quotes if desired
    if criteria[5] == 1:
        # traditional to simplified
        if (criteria[6]):
            # use smart quotes
            htmlstr_corrected = trad_to_simp_smart_re.sub(lambda match: trad_to_simp_smart_quotes[match.group(0)], data)
        else:
            # use full width standard quotes
            htmlstr_corrected = trad_to_simp_re.sub(lambda match: trad_to_simp_quotes[match.group(0)], data)
    elif criteria[5] == 2:
        # simplified to traditional
        # replace trailing full width double quotes using 」
        htmlstrA = re.sub(r'(＂(?:(?!＂).)*)＂((?:(?!＂).)*)', r'\1」\2', data)
        # replace trailing full width single quotes using 』
        htmlstrB = re.sub(r'(＇(?:(?!＇).)*)＇((?:(?!＇).)*)', r'\1』\2', htmlstrA)
        # replace leading full width double quotes using 「
        htmlstrC = htmlstrB.replace('＂', '「')
        # replace leading full width single quotes using 『
        htmlstrD = htmlstrC.replace('＇', '『')
        # replace any curved double quotes
        htmlstr_corrected = simp_to_trad_re.sub(lambda match: simp_to_trad_quotes[match.group(0)], htmlstrD)
    else:
        # no quote changes desired
        htmlstr_corrected = data
    return htmlstr_corrected

# multiple_replace copied from ActiveState http://code.activestate.com/recipes/81330-single-pass-multiple-replace/
# Copyright 2001 Xavier Defrang
# PSF (Python Software Foundation) license (GPL Compatible)
# https://docs.python.org/3/license.html
def multiple_replace(orientation_regex, orientation_dict, text):
#  # Create a regular expression  from the dictionary keys
#  regex = re.compile("(%s)" % "|".join(map(re.escape, orientation_dict.keys())))

  # For each match, look-up corresponding value in dictionary
  return orientation_regex.sub(lambda mo: orientation_dict[mo.string[mo.start():mo.end()]], text)

def get_language_code(criteria):
    """
    :param criteria: the description of the desired conversion
    :return: 'zh-CN', 'zh-TW', 'zh-HK', or 'None'
    """
    conversion_mode = criteria[1]
    input_type = criteria[2]
    output_type = criteria[3]
    use_target_phrasing = criteria[4]

    language_code = 'None'

    if conversion_mode == 1:
        #trad to simp, output type is always mainland (we don't yet support Malaysia/Singapore zh-SG)
        language_code = 'zh-CN'

    elif conversion_mode == 2:
        #simp to trad, (we don't support Macau yet zh-MO)
        if output_type == 0:
            language_code = 'zh-CN'
        elif output_type == 1:
            language_code = 'zh-HK'
        else:
            language_code = 'zh-TW'

    elif conversion_mode == 3:
        #trad to trad, (we don't support Macau yet zh-MO)
        if input_type == 0:
            if output_type == 1:
                language_code = 'zh-HK'
            elif output_type == 2:
                language_code = 'zh-TW'
            else:
                #mainland trad -> mainland trad does nothing
                language_code = 'None'
        else:
            #hk -> tw and tw -> hk not currently set up
            #hk -> hk and tw -> tw does nothing
            language_code = 'None'
    return language_code

def set_metadata_toc(container, language, criteria, changed_files, converter):
    # Returns True if either the metadata or TOC files changed
    # changed_files is updated
    
    opfChanged = False
    tocChanged = False
    # List of dc items in OPF file that get a simple text replacement
    # Add more items to this list if needed
    dc_list = ['//opf:metadata/dc:title',
               '//opf:metadata/dc:description',
               '//opf:metadata/dc:publisher',
               '//opf:metadata/dc:subject'
               '//opf:metadata/dc:contributor',
               '//opf:metadata/dc:coverage',
               '//opf:metadata/dc:rights'];
    # Update the OPF metadata
    # The language and creator fields are special
    # Only update the dc language if the original language was a Chinese type and epub format
    if container.book_type == u'epub':
        items = container.opf_xpath('//opf:metadata/dc:language')
        if len(items) > 0:
            for item in items:
                old_item = item.text
                if re.search('zh-\w+|zh', item.text, flags=re.IGNORECASE) != None:
                    item.text = language
                if item.text != old_item:
                    opfChanged = True
        # Update the creator text and file-as attribute
    items = container.opf_xpath('//opf:metadata/dc:creator')
    if len(items) > 0:
        for item in items:
            old_item = item.text
            if (item.text != None):
                item.text = converter.convert(item.text)
                if item.text != old_item:
                    opfChanged = True
            for attribute in item.attrib: # update file-as attribute
                item.attrib[attribute] = converter.convert(item.attrib[attribute])
    # Update the remaining dc items using a loop
    for dc_item in dc_list:
        items = container.opf_xpath(dc_item)
        if len(items) > 0:
            for item in items:
                old_item = item.text
                if (item.text != None):
                    item.text = converter.convert(item.text)
                    if item.text != old_item:
                        opfChanged = True

    # Update the TOC - Do this after modifying the OPF data
    # Just grab all <text> fields (AKA "title" attribute in a TOC object)
    # and convert to the desired Chinese. Let Calibre set the title and
    # language automatically from the OPF file modified earlier
    book_toc = get_toc(container)
    for item in book_toc.iterdescendants():
        old_title = item.title
        item.title = converter.convert(item.title)
        if old_title != item.title:
            tocChanged = True

    # Update the files with the changes
    if tocChanged:
        commit_toc(container, book_toc)
        container.dirty(book_toc.toc_file_name)
        changed_files.append(book_toc.toc_file_name)
    if opfChanged:
        container.dirty(container.opf_name)
        changed_files.append(container.opf_name)
    return(tocChanged or opfChanged)


def add_flow_direction_properties(rule, orientation_value, break_value):
    rule_changed = False
    if rule.style['writing-mode'] != orientation_value:
        rule.style['writing-mode'] = orientation_value
        rule_changed = True

    if rule.style['-epub-writing-mode'] != orientation_value:
        rule.style['-epub-writing-mode'] = orientation_value
        rule_changed = True

    if rule.style['-webkit-writing-mode'] != orientation_value:
        rule.style['-webkit-writing-mode'] = orientation_value
        rule_changed = True

    if rule.style['line-break'] != break_value:
        rule.style['line-break'] = break_value
        rule_changed = True

    if rule.style['-webkit-line-break'] != break_value:
        rule.style['-webkit-line-break'] = break_value
        rule_changed = True

    return rule_changed

def set_flow_direction(container, language, criteria, changed_files, converter):
    # Open OPF and set flow
    flow = 'default'
    if criteria[7] == 2:
        flow = 'rtl'
    elif criteria[7] == 1:
        flow = 'ltr'
    # Look for the 'spine' element and change the direction attribute
    items = container.opf_xpath('//opf:spine')
    fileChanged = False
    if len(items) > 0:
        for item in items:
            if 'page-progression-direction' in item.attrib:
                if item.attrib['page-progression-direction'] != flow:
                    fileChanged = True
            else:
                fileChanged = True
            item.attrib['page-progression-direction'] = flow
    if fileChanged:
        container.dirty(container.opf_name)
        if container.opf_name not in changed_files:
            changed_files.append(container.opf_name)
    # Open CSS and set layout direction in the body section
    if criteria[7] == 1:
        orientation = 'horizontal-tb'
        orientation_azw3 = 'horizontal-lr'
        break_rule = 'auto'
    if criteria[7] == 2:
        orientation = 'vertical-rl'
        orientation_azw3 = 'vertical-rl'
        break_rule = 'normal'

    if container.book_type == u'azw3':
        items = container.opf_xpath('//opf:metadata/opf:meta')
        found_name = False
        if len(items) > 0:
            for item in items:
                if 'name' in item.attrib and 'content' in item.attrib:
                    if item.attrib['name'] == 'primary-writing-mode':
                        found_name = True
                        if item.attrib['content'] != orientation_azw3:
                            item.attrib['content'] = orientation_azw3
                            fileChanged = True

        if found_name == False:
            #Create a meta tag with attributes
            metadata = container.opf_xpath('//opf:metadata')[0]
            item = metadata.makeelement('meta')
            item.set('name', 'primary-writing-mode')
            item.set('content', orientation_azw3)
            container.insert_into_xml(metadata, item)
            fileChanged = True

        if fileChanged:
            container.dirty(container.opf_name)
            if container.opf_name not in changed_files:
                changed_files.append(container.opf_name)

    addedCSSRules = False

    # Loop through all the files in the ebook looking for CSS style sheets
    # Update the CSS .calibre class if this was a Calibre converted file
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES:
            # Get the sheet as a python cssutils CSSStyleSheet object
            sheet = container.parsed(name)
            # If this is a Calibre created ebook, add CSS rules to .calibre class
            rules = (rule for rule in sheet if rule.type == rule.STYLE_RULE)
            for rule in rules:
                for selector in rule.selectorList:
                    if selector.selectorText == u'.calibre':
                        addedCSSRules = True
                        if add_flow_direction_properties(rule, orientation, break_rule):
                            fileChanged = True
                            changed_files.append(name)
                            container.dirty(name)
                        break

    if not addedCSSRules:
        for name, mt in container.mime_map.iteritems():
            if mt in OEB_STYLES:
                # Get the sheet as a python cssutils CSSStyleSheet object
                sheet = container.parsed(name)
                # Look through all the rules and find any with a 'body' selector
                rules = (rule for rule in sheet if rule.type == rule.STYLE_RULE)
                for rule in rules:
                    for selector in rule.selectorList:
                        if selector.selectorText == u'body':
                            addedCSSRules = True
                            if add_flow_direction_properties(rule, orientation, break_rule):
                                fileChanged = True
                                changed_files.append(name)
                                container.dirty(name)

    # If no 'body' selector rule is found in any css file, add one to every css file
    if not addedCSSRules:
        for name, mt in container.mime_map.iteritems():
            if mt in OEB_STYLES:
                # Get the sheet as a python cssutils CSSStyleSheet object
                sheet = container.parsed(name)
                # Create a style rule for body.
                styleEntry = css.CSSStyleDeclaration()
                styleEntry['writing-mode'] = orientation
                styleRule = css.CSSStyleRule(selectorText=u'body', style=styleEntry)
                sheet.add(styleRule)
                styleRule.style['-epub-writing-mode'] = orientation
                styleRule.style['-webkit-writing-mode'] = orientation
                styleRule.style['line-break'] = break_rule
                styleRule.style['-webkit-line-break'] = break_rule
                fileChanged = True
                changed_files.append(name)
                container.dirty(name)
    return fileChanged

def get_configuration(criteria):
    """
    :param criteria: the description of the desired conversion
    :return: 'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', 'tw2sp', 'no_convert', or 'None'
    """
    conversion_mode = criteria[1]
    input_type = criteria[2]
    output_type = criteria[3]
    use_target_phrasing = criteria[4]

    configuration = ''

    if conversion_mode == 0:
        #no conversion desired
        configuration = 'no_convert'

    elif conversion_mode == 1:
        #trad to simp, output type is always mainland
        if input_type == 0:
            configuration = 't2s'
        elif input_type == 1:
            configuration = 'hk2s'
        else:
            configuration = 'tw2s'
            if use_target_phrasing:
                configuration += 'p'

    elif conversion_mode == 2:
        #simp to trad, input type is always mainland
        configuration = 's'
        if output_type == 0:
            configuration += '2t'
        elif output_type == 1:
            configuration += '2hk'
        else:
            configuration += '2tw'
            if use_target_phrasing:
                configuration += 'p'

    else:
        #trad to trad
        if input_type == 0:
            if output_type == 1:
                configuration = 't2hk'
            elif output_type == 2:
                configuration = 't2tw'
            else:
                #mainland trad -> mainland trad does nothing
                configuration = 'None'
        else:
            #hk -> tw, tw -> hk,  tw -> mainland, and hk -> mainland not currently set up
            #hk -> hk and tw -> tw does nothing
            configuration = 'None'
    return configuration

def cli_convert_text(data, criteria, language, converter):
    from calibre_plugins.chinese_text.resources.utilities import tokenize

    htmlstr_corrected = replace_quotations(data, criteria)

    tokens = tokenize(htmlstr_corrected)
    result = []
    for cur_token in tokens:
        if cur_token[0] == "tag":
            # change language code inside of tags
            if criteria[0] != 0:
                result.append(_zh_re.sub(self.language, cur_token[1]))
            else:
                result.append(cur_token[1])
        else:
            # Update punctuation based on text direction if needed
            if criteria[8] != 0:
                if criteria[7] == 1:
                    cur_token[1] = multiple_replace(_v2h_dict_regex, _v2h_dict, cur_token[1])
                elif criteria[7] == 2:
                    if criteria[8] == 1:
                        cur_token[1] = multiple_replace(_h2v_dict_regex, _h2v_dict, cur_token[1])
                    else:
                        cur_token[1] = multiple_replace(_h2vkindle_dict_regex, _h2vkindle_dict, cur_token[1])
            # Convert text if needed
            if criteria[1] != 0:
                result.append(converter.convert(cur_token[1]))
            else:
                result.append(cur_token[1])
    return "".join(result)

def cli_get_criteria(args):
    #Note: criteria is a tuple of the form:
    #criteria = (
    #        process_single_file(BOOL), output_mode(INT), input_locale(INT),
    #        output_locale(INT), use_target_phrases(BOOL), quote_type(INT)),
    #        smart_quotes(BOOL), text_direction(INT)
    #   process_single_file:    True - In editor only process a selected file in ebook
    #                           False - Process all files in ebook
    #   output_mode:    0 = no change
    #                   1 = traditional->simplified
    #                   2 = simplified->traditional
    #                   3 = traditional->traditional
    #   input_locale:   0 = Mainland, 1 = Hong Kong, 2 = Taiwan
    #   output_local:   0 = Mainland, 1 = Hong Kong, 2 = Taiwan
    #   use_target_phrase:  True - Modify text to use words associated with target locale
    #   quote_type:     0 = No change, 1 = Western, 2 = East Asian
    #   use_smart_quotes:   True - Use curves quotation marks if quote_type is Western
    #   text_direction: 0 = No change, 1 = Horizontal, 2 = Vertical
    #   optimization:   0 = No change, 1 = Readium, 2 = Kindle

    # Set up default values
    process_single_file = False
    output_mode = 0           # None 
    input_locale = 0          # Mainland
    output_locale = 0         # Mainland
    use_target_phrase = False
    quote_type = 0            # No change
    use_smart_quotes = True
    text_direction = 0        # No change
    optimization = 0          # No change
    

    if args.direction_opt == 't2s':
        output_mode = 1
    elif args.direction_opt == 's2t':
        output_mode = 2
    elif args.direction_opt == 't2t':
        output_mode = 3

    if args.orig_opt == 'hk':
        input_locale = 1
    elif args.orig_opt == 'tw':
        input_locale = 2

    if args.dest_opt == 'hk':
        output_locale = 1
    elif args.dest_opt == 'tw':
        output_locale = 2
        
    use_target_phrase = args.phrase_opt

    if args.quote_type_opt == 'w':
        quote_type = 1
    elif args.quote_type_opt == 'e':
        quote_type = 2

    if args.text_dir_opt == 'h':
        text_direction = 1
    elif args.text_dir_opt == 'v':
        text_direction = 2

    use_smart_quotes = args.smart_quotes_opt

    if args.optimization_opt == 'r':
        optimization = 1
    elif args.optimization_opt == 'k':
        optimization = 2
    
    criteria = (
        process_single_file, output_mode, input_locale,
        output_locale, use_target_phrase, quote_type,
        use_smart_quotes, text_direction, optimization)
    return criteria

def cli_process_files(criteria, container, converter):
    from hashlib import md5
    lang = get_language_code(criteria)

    # Cover the entire book
    # Set metadata and Table of Contents (TOC)
    changed_files = []
    if criteria[1] != 0:
        set_metadata_toc(container, lang, criteria, changed_files, converter)

    # Set text orientation
    if criteria[7] != 0:
        direction_changed = set_flow_direction(container, lang, criteria, changed_files, converter)

    # Cover the text
    file_list = [i[0] for i in container.mime_map.items() if i[1] in OEB_DOCS]
    clean = True
    for name in file_list:
        data = container.raw_data(name)
        orig_hash = md5(data).digest()
        htmlstr = cli_convert_text(data, criteria, lang, converter)
        new_hash = md5(htmlstr).digest()
        if new_hash != orig_hash:
            container.dirty(name)
            container.open(name, 'wb').write(htmlstr)
            changed_files.append(name)
            clean = False

    return(changed_files)

def print_conversion_info(args, file_set, version, configuration_filename):
    print('')
    print(_('Plugin version: ') + str(version[0]) + '.' + str(version[1]) + '.' + str(version[2]))
    if args.direction_opt != 'none':
        print(_('Configuration file: '), configuration_filename)
    print(_('Output direction: '), end="")
    if args.direction_opt == 'none':
        print(_('No change'))
    elif args.direction_opt == 't2s':
        print(_('Traditional->Simplified'))
    elif args.direction_opt == 's2t':
        print(_('Simplified->Traditional'))
    else:
        print(_('Traditional->Traditional'))
    if args.direction_opt != 'none':
        print(_('Chinese input locale: ') + args.orig_opt.upper())
        print(_('Chinese output locale: ') + args.dest_opt.upper())
        print(_('Use destination phrases: ') + str(args.phrase_opt))

    print(_('Quotation Mark Style: '), end="")
    if args.quote_type_opt == 'no_change':
        print(_('No Change'))
    elif args.quote_type_opt == 'w':
        print(_('Western'))
        if args.smart_quotes_opt:
            print(_('Using smart quotes'))
        else:
            print(_('Using standard quotes'))
    else:
        print(_('East Asian'))

    print(_('Text direction: '), end="")
    if args.text_dir_opt == 'no_change':
        print('No Change')
    elif args.text_dir_opt == 'h':
        print(_('Horizontal'))
    else:
        print (_('Vertical'))

    if args.text_dir_opt != 'no_change':
         print(_('Text presentation optimization: '), end="")
         if args.optimization_opt == 'r':
             print(_('Readium'))
         elif args.optimization_opt == 'k':
             print(_('Kindle'))
         else:
             print(_('None'))

    if args.outdir_opt == None and args.append_suffix_opt == '':
        print(_('Output directory: Overwrite existing file'))
    elif args.outdir_opt == None:
        print(_('Output directory: Same directory as input file'))
    else:
        print(_('Output directory: ') + args.outdir_opt)
    print(_('Output file basename suffix: ') + args.append_suffix_opt)
    print(len(file_set), _(' File(s) will be converted:'))
    for filename in file_set:
        print('   ' + filename)
    print('')
    
def main(argv, plugin_version, usage=None):
    import argparse
    import glob

    converter = OpenCC()
    criteria = None

    list_of_locales = ['cn', 'hk', 'tw']
    list_of_directions = ['t2s', 's2t', 't2t', 'none']
    quotation_types = ['w', 'e', 'no_change']
    text_directions = ['h', 'v', 'no_change']
    optimization = ['r', 'k', 'none']

    parser = argparse.ArgumentParser(description=_('Convert Chinese characters between traditional/simplified types and/or change text style.\nPlugin Version: ') +
                                     str(plugin_version[0]) + '.' + str(plugin_version[1]) + '.' + str(plugin_version[2]))
    parser.add_argument('-il', '--input-locale', dest='orig_opt', default='cn',
                        help=_('Set to the ebook origin locale if known (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-ol', '--output-locale', dest='dest_opt', default='cn',
                        help=_('Set to the ebook target locale (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-d', '--direction', dest='direction_opt', default='none',
                        help=_('Set to the ebook conversion direction (Default: none)'), choices=list_of_directions)
    parser.add_argument('-p', '--phrase_convert', dest='phrase_opt', help=_('Convert phrases to target locale versions (Default: False)'),
                        action='store_true')

    parser.add_argument('-qt', '--quotation-type', dest='quote_type_opt', default='no_change',
                        help=_('Set to the ebook origin locale if known (Default: no_change)'), choices=quotation_types)
    parser.add_argument('-sq', '--smart_quotes', dest='smart_quotes_opt', help=_('Use smart quotes if applicable (Default: False)'),
                        action='store_true')
    parser.add_argument('-td', '--text-direction', dest='text_dir_opt', default='no_change',
                        help=_('Set to the ebook origin locale if known (Default: no_change)'), choices=text_directions)
    parser.add_argument('-tdo', '--text-device-optimize', dest='optimization_opt', help=_('Optimize text for device (Default: none)'),
                        choices=optimization)

    parser.add_argument('-v', '--verbose', dest='verbose_opt', help=_('Print out details as the conversion progresses (Default: False)'),
                        action='store_true')
    parser.add_argument('-t', '--test', dest='test_opt', help=_('Run conversion operations without saving results (Default: False)'),
                        action='store_true')
    parser.add_argument('-q', '--quiet', dest='quiet_opt', help=_('Do not print anything, ignore warnings - this option overides the -s option (Default: False)'),
                        action='store_true')
    parser.add_argument('-od', '--output-dir', dest='outdir_opt',
                        help=_('Set to the ebook output file directory (Default: overwrite existing ebook file)'))
    parser.add_argument('-a', '--append_suffix', dest='append_suffix_opt', default='',
                        help=_('Append a suffix to the output file basename (Default: '')'))
    parser.add_argument('-f', '--force', dest='force_opt', help=_('Force processing by ignoring warnings (e.g. allow overwriting files with no prompt)'),
                        action='store_true')
    parser.add_argument('-s', '--show', dest='show_opt', help=_('Show the settings based on user cmdline options and exit (Default: False)'),
                        action='store_true')
    parser.add_argument('ebookFiles', metavar='ebook-filepath', nargs='+',
                        help=_('One or more epub and/or azw3 ebook filepaths - UNIX style wildcards accepted'))

    args = parser.parse_args(argv)
    
    #Pull out the list of ebooks
    file_set = set()

    if args.outdir_opt == None:
        output_dir = None
                               
    else:
        dir_list = glob.glob(args.outdir_opt)
        if len(dir_list) == 0:
            if not args.quiet_opt:
                print(_('Output directory not found'))
            return(1)
        elif len(dir_list) > 1:
            if not args.quiet_opt:
                print(_('Multiple output directory not found - only one allowed:'))
                for dir in dir_list:
                    print(dir)
            return(1)
        else:
            output_dir = os.path.abspath(dir_list[0])
            if not os.path.isdir(output_dir):
                if not args.quiet_opt:
                    print(_('Output directory not a directory'))
                return(1)
        
    for filespec in args.ebookFiles:
        #Get a list of files
        file_list = glob.glob(filespec)
        for filename in file_list:
            #Discard any non-files
            if not os.path.isfile(filename):
                if not args.quiet_opt:
                    print(_('Discarding - Not a file: ') + filename)
                continue
            #Discard any files not ending in ebook
            if not filename.lower().endswith(".epub") and not filename.lower().endswith(".azw3"):
                if not args.quiet_opt:
                    print(_('Discarding - Does not end in \'.epub\' or \'.azw3\': ') + filename)
                continue
            #Add filename to set
            file_set.add(filename)

    #Determine the conversion criteria tuple values
    criteria = cli_get_criteria(args)

    #set convertor properties
    conversion = get_configuration(criteria)
    if conversion == 'None':
        if not args.quiet_opt:
            print_conversion_info(args, file_set, plugin_version, '??')
            print(_('The input/output/direction combination selected is not supported.\n Please use a different input/output/direction combination'))
        return(1)
    elif conversion == 'no_convert':
        pass
    else:
        if args.verbose_opt and not args.quiet_opt:
            print(_('Using opencc-python conversion configuration file: ') + conversion + '.json')
        converter.set_conversion(conversion)

    #Print out the conversion info
    if not args.quiet_opt:
        print_conversion_info(args, file_set, plugin_version, conversion + '.json')

    #If show option given, exit after displaying settings
    if args.show_opt:
        return(0)

    if (args.outdir_opt == None) and args.append_suffix_opt == '':
        if not args.force_opt:
            response = str(raw_input(_('No output directory specified, original ebook file will be overwritten. Is this OK? [N] or Y: '))).lower().strip()
            if (len(response)) > 0 and (response[0] == 'y'):
                pass
            else:
                print(_('Exiting without changes'))
                return(0)

    if len(file_set) == 0:
        if not args.quiet_opt:
            print(_('No ebook files specified!'))
            return(0)

    #Loop through the filenames
    for filename in file_set:
        #Print out the current operation
        if not args.quiet_opt:
            print(_('Converting ebook: ') + os.path.basename(filename + ' .... '), end="")
        #Create a Container object from the file
        container = get_container(filename)
        #Update the container
        changed_files = cli_process_files(criteria, container, converter)
        if (len(changed_files) > 0) and not args.quiet_opt:
            print(_('Changed'))
            if args.verbose_opt:
                for changed_file_name in changed_files:
                    print('   ' + changed_file_name)
        else:
            if not args.quiet_opt:
                print(_('Unchanged'))
        #if changes, save the container as an ebook file with a name based on the conversion criteria
        if len(changed_files) > 0:
            if (args.outdir_opt == None) and (args.append_suffix_opt == ''):
                if not args.quiet_opt:
                    print(_('   Overwriting file with changes: ') + filename, end="")
                    if  args.test_opt:
                        print(_('   --- TEST MODE - No Changes Written'))
                    else:
                        print('')
                if not args.test_opt:
                    container.commit()
            else:
                #Create absolute path to filename. Earlier code already verified that it ends in '.epub' or '.azw3'
                file_path_portion, file_name_portion = os.path.split(filename)
                adjusted_file_name = file_name_portion[:-5] + args.append_suffix_opt + file_name_portion[-5:]
                if args.outdir_opt != None:
                    output_path = os.path.join(output_dir, adjusted_file_name)
                else:
                    output_path = os.path.join(file_path_portion, adjusted_file_name)
                if not args.quiet_opt:
                    print(_('   Saving file to: ') + output_path, end="")
                    if  args.test_opt:
                        print(_('   --- TEST MODE - No Changes Written'))
                    else:
                        print('')
                if not args.test_opt:
                    container.commit(outpath=output_path)

    return(0)


    
if __name__ == "__main__":
    main(sys.argv[1:])

