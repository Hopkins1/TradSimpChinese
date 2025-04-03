# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2022, Hopkins'

import re, os.path
from css_parser import  css, stylesheets
from html.parser import HTMLParser
from html.entities import name2codepoint

try:
    from qt.core import (Qt, QAction, QDialog, QApplication, QCursor)
except ImportError:
    from PyQt5.Qt import (Qt, QAction, QDialog, QApplication, QCursor)


from calibre.gui2.tweak_book.plugin import Tool
from calibre.gui2.tweak_book import editor_name
from calibre.gui2 import error_dialog, info_dialog
from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, get_container
try:
    from calibre.ebooks.oeb.polish.toc import get_toc, find_existing_ncx_toc, commit_toc
except:
    from calibre.ebooks.oeb.polish.toc import get_toc, find_existing_toc, commit_toc

from calibre_plugins.chinese_text.__init__ import (PLUGIN_NAME, PLUGIN_SAFE_NAME)
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


CONFIG_FILE = 'config'
DICT_FILE = 'dictionary'


# Default punctuation characters that are not enabled. Used to set the values for default button in
# the punctuation dialog. Vertical presentation forms of these are not generally used in vertical text.
# List was derived by examining actual vertical text epub books.
PUNC_OMITS = "。、；：！？…‥＿﹏，"


# Index into criteria      criteria values

INPUT_SOURCE = 0           # 0=whole book, 1=current file, 2=selected text
CONVERSION_TYPE = 1        # 0=No change, 1=trad->simp, 2=simp->trad, 3=trad->trad
INPUT_LOCALE = 2           # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
OUTPUT_LOCALE = 3          # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
USE_TARGET_PHRASES = 4     # True/False
QUOTATION_TYPE = 5         # 0=No change, 1=Western, 2=East Asian
OUTPUT_ORIENTATION = 6     # 0=No change, 1=Horizontal, 2=Vertical
UPDATE_PUNCTUATION = 7     # True/False
PUNC_DICT = 8              # punctuation swapping dictionary based on settings, may be None
PUNC_REGEX = 9             # precompiled regex expression to swap punctuation, may be None


#<!--PI_SELTEXT_START-->
seltext_start_tag = "PI_SELTEXT_START"

#<!--PI_SELTEXT_END-->
seltext_end_tag   = "PI_SELTEXT_END"

# Horizontal full width characters to their vertical presentation forms lookup before punctuation dialog
# modification
_h2v_master_dict = {'。':'︒', '、':'︑', '；':'︔', '：':'︓', '！':'︕', '？':'︖', '「':'﹁', '」':'﹂', '〈':'︿', '〉':'﹀',
        '『':'﹃', '』':'﹄', '《':'︽', '》':'︾', '【':'︻', '（':'︵', '】':'︼', '）':'︶','〖': '︗', '〗':'︘',
        '〔':'︹', '｛':'︷', '〕':'︺', '｝':'︸', '［':'﹇', '］':'﹈', '…':'︙', '‥':'︰', '—':'︱', '＿':'︳',
        '﹏':'︴', '，':'︐'}


# Calibre function passed into converter for getting resource files
def get_resource_file(file_type, file_name):
    if file_type == CONFIG_FILE:
        return get_resources('resources/opencc_python/config/' + file_name)
    elif file_type == DICT_FILE:
        return get_resources('resources/opencc_python/dictionary/' + file_name)
    else:
        raise ValueError('conversion value incorrect')


# regular expression to remove ruby text
# newstring = oldstring.replace(/<rb>([^<]*)<\/rb>|<rp>[^<]*<\/rp>|<rt>[^<]*<\/rt>|<\/?ruby>/g, "$1");

class HTML_TextProcessor(HTMLParser):
    """
    This class takes in HTML files as a string.
    """

    def __init__(self, textConvertor = None):
          super().__init__(convert_charrefs=False)
          self.recording = 0
          self.result = []
          self.textConverter = textConvertor
          self.criteria = None
          self.converting = True
          self.language = None

          # Create regular expressions to modify quote styles
          self.trad_to_simp_quotes = {'「':'“', '」':'”', '『':'‘', '』':'’'}
          self.trad_to_simp_re = re.compile('|'.join(map(re.escape, self.trad_to_simp_quotes)))

          self.simp_to_trad_quotes = {'“':'「', '”':'」', '‘':'『', '’':'』'}
          self.simp_to_trad_re = re.compile('|'.join(map(re.escape, self.simp_to_trad_quotes)))

          # Create regular expression to look for common transliterated Chinese lang attributes
          self.zh_non_re = re.compile(r'lang=\"zh-Latn|lang=\"zh-Cyrl|lang=\"zh-Bopo|lang=\"zh-Mong', re.IGNORECASE)

          # Create regular expression to modify lang attribute
          self.zh_re = re.compile(r'lang=\"zh-[\-\w+]+\"|lang=\"zh\"', re.IGNORECASE)


    # Use this if one wants to reset the converter
    def setTextConvertor(self, textConvertor):
        self.textConverter = textConvertor

    def setLanguageAttribute(self, language):
        self.language = language

    def replace_quotations(self, data):
        # update quotes if desired
        if self.criteria[QUOTATION_TYPE] == 1:
            # traditional to simplified
            htmlstr_corrected = self.trad_to_simp_re.sub(lambda match: self.trad_to_simp_quotes[match.group(0)], data)
        elif self.criteria[QUOTATION_TYPE] == 2:
            # simplified to traditional
            htmlstr_corrected = self.simp_to_trad_re.sub(lambda match: self.simp_to_trad_quotes[match.group(0)], data)
        else:
            # no quote changes desired
            htmlstr_corrected = data
        return htmlstr_corrected


    # multiple_replace copied from ActiveState http://code.activestate.com/recipes/81330-single-pass-multiple-replace/
    # Copyright 2001 Xavier Defrang
    # PSF (Python Software Foundation) license (GPL Compatible)
    # https://docs.python.org/3/license.html
    def multiple_replace(self, replace_regex, replace_dict, text):
      # For each match, look-up corresponding value in dictionary
      return replace_regex.sub(lambda mo: replace_dict[mo.string[mo.start():mo.end()]], text)

    def processText(self, data, criteria):
##        print("processText:", data)
##        print('processText Criteria: ', criteria)

        self.criteria = criteria
        self.result.clear()
        self.reset()
        if self.criteria[INPUT_SOURCE] == 2:
            # turn off converting until a start comment seen
            self.converting = False
        else:
            self.converting = True

##        print("Feeding in text")
        self.feed(data)
        self.close()
        # return result
        return "".join(self.result)

    def handle_starttag(self, tag, attrs):
##        print("Literal start tag:", self.get_starttag_text())
##        print("Start tag:", tag)
##        for attr in attrs:
##            print("     attr:", attr)

        # change language code inside of tags if Chinese script
        if self.converting and (self.criteria[CONVERSION_TYPE] != 0) and (self.language != None) and (self.zh_non_re.search(self.get_starttag_text()) == None):
            self.result.append(self.zh_re.sub(self.language, self.get_starttag_text()))
        else:
            self.result.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.result.append("</" + tag + ">")

##        print("End tag  :", tag)

    def handle_startendtag(self, tag,  attrs):
##        print("Literal start-end tag:", self.get_starttag_text())
##        print("Strt-End tag     :", tag)
##        for attr in attrs:
##            print("     attr:", attr)

        # change language code inside of tags if Chinese script
        if (self.criteria[INPUT_SOURCE] == 0) and (self.criteria[CONVERSION_TYPE] != 0) and (self.language != None) and (self.zh_non_re.search(self.get_starttag_text()) == None):
            self.result.append(self.zh_re.sub(self.language, self.get_starttag_text()))
        else:
            self.result.append(self.get_starttag_text())

    def handle_data(self, text):
##        print("Data     :", text)

        if text.isspace():
##            print("handle_data is only whitespace")
            self.result.append(text)
        else:
            if self.converting:
                if (self.criteria[OUTPUT_ORIENTATION] == 0) or (self.criteria[OUTPUT_ORIENTATION] == 2):
                    # Convert quotation marks
                    if (self.criteria[QUOTATION_TYPE] != 0):
                        text = self.replace_quotations(text)

                # Convert punctuation to vertical or horizontal using provided regular expression
                # self.criteria[PUNC_REGEX] is only set if vertical or horizontal change selected
                if self.criteria[PUNC_REGEX] != None:
                    text = self.multiple_replace(self.criteria[PUNC_REGEX], self.criteria[PUNC_DICT], text)

                if (self.criteria[OUTPUT_ORIENTATION] == 1):
                    # Convert quotation marks
                    if (self.criteria[QUOTATION_TYPE] != 0):
                        text = self.replace_quotations(text)

            # Convert text to traditional or simplified if needed
##            print('handle_data CONVERSION_TYPE criteria = ', self.criteria[CONVERSION_TYPE])
            if self.criteria[CONVERSION_TYPE] != 0 and self.converting:
##                print('handle_data calling self.textConverter.convert(text)')
                self.result.append(self.textConverter.convert(text))
            else:
##                print('handle_data NOT calling self.textConverter.convert(text)')
                self.result.append(text)


    def handle_comment(self, data):
##        print('handle_comment raw data:', data)
##        print('handle_comment stripped data:', data.strip())
##        print('seltext_start_tag:', seltext_start_tag)
##        print('seltext_end_tag:', seltext_end_tag)
##        print('handle_comment self.criteria[INPUT_SOURCE]:', self.criteria[INPUT_SOURCE])
        if (self.criteria[INPUT_SOURCE] == 2) and (data.strip() == seltext_start_tag):
            self.converting = True
##            print('handle_comment converting set to True')
        elif (self.criteria[INPUT_SOURCE] == 2) and (data.strip() == seltext_end_tag):
            self.converting = False
##            print('handle_comment converting set to False')
        self.result.append("<!--" + data + "-->")
##        print("Comment  :", data)

    def handle_pi(self, data):
        self.result.append("<?" + data + ">")
##        print("<?  :", data)

    def handle_entityref(self, name):
        self.result.append("&" + name + ";")
##        c = chr(name2codepoint[name])
##        print("Named ent:", c)
##
    def handle_charref(self, name):
        self.result.append("&#" + name + ";")
##        if name.startswith('x'):
##            c = chr(int(name[1:], 16))
##        else:
##            c = chr(int(name))
##        print("Num ent  :", c)

    def handle_decl(self, data):
        self.result.append("<!" + data + ">")
##        print("Decl     :", data)

    def unknown_decl(self, data):
        self.result.append("<!" + data + ">")
##        print("Unknown Decl     :", data)


class TradSimpChinese(Tool):
    from calibre_plugins.chinese_text.resources.opencc_python.opencc import OpenCC

    converter = OpenCC(get_resource_file)

    # Create the HTML parser and pass in the converer
    parser = HTML_TextProcessor(converter)

    name = 'trad-simp-chinese'

    # If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    # If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    # The interface dialog
    dlg = None

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

        # Initialize defaults for preferences
        self.prefs = getPrefs()
        self.prefsPrep()
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

        if self.dlg == None:
            self.dlg = ConversionDialog(self.gui, self.prefs, _h2v_master_dict, PUNC_OMITS)
        if self.dlg.exec_():
            criteria = self.getCriteria()
            # Ensure any in progress editing the user is doing is present in the container
            self.boss.commit_all_editors_to_container()
            self.boss.add_savepoint(_('Before: Text Conversion'))

            # Set the conversion output language
            self.language = get_language_code(criteria)
            if self.language != "None":
                self.parser.setLanguageAttribute('lang=\"' + self.language + '\"')
            else:
                self.parser.setLanguageAttribute(None)

            try:
                conversion = get_configuration(criteria)
##                print("Conversion: ", conversion);
                if conversion == 'unsupported_conversion':
                    info_dialog(self.gui, _('No Changes'),
                    _('The output configuration selected is not supported.\n Please use a different Input/Output Language Styles combination'), show=True)
                else:
                    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
                    QApplication.processEvents()
                    self.converter.set_conversion(conversion)
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
                elif conversion != 'unsupported_conversion':
                    info_dialog(self.gui, _('No Changes'),
                                _('No text meeting your criteria was found to change.\nNo changes made.'), show=True)

    def process_files(self, criteria):
        container = self.current_container  # The book being edited as a container object

        if criteria[INPUT_SOURCE] == 1 or criteria[INPUT_SOURCE] == 2:
            # Only convert the selected file
            name = editor_name(self.gui.central.current_editor)
            if not name or container.mime_map[name] not in OEB_DOCS:
                return info_dialog(self.gui, _('Cannot Process'),
                        _('No file open for editing or the current file is not an (x)html file.'), show=True)

            data = container.raw_data(name)
            htmlstr = self.parser.processText(data, criteria)
            if htmlstr != data:
                self.filesChanged = True
                self.changed_files.append(name)
                container.open(name, 'w').write(htmlstr)

        elif criteria[INPUT_SOURCE] == 0:
            # Cover the entire book
            # Set metadata and Table of Contents (TOC) if language changed
            if criteria[CONVERSION_TYPE] != 0:
                self.filesChanged = set_metadata_toc(container, self.language, criteria, self.changed_files, self.converter)

            # Check for orientation change
            direction_changed = False
            if criteria[OUTPUT_ORIENTATION] != 0:
                direction_changed = set_flow_direction(container, criteria, self.changed_files, self.converter)

            # Cover the text portion
            from calibre_plugins.chinese_text.resources.dialogs import ShowProgressDialog
            d = ShowProgressDialog(self.gui, container, OEB_DOCS, criteria, self.parser.processText, _('Converting'))
            cancelled_msg = ''
            if d.wasCanceled():
                cancelled_msg = ' (cancelled)'
            self.filesChanged = self.filesChanged or (not d.clean) or direction_changed
            self.changed_files.extend(d.changed_files)

    def prefsPrep(self):
        # Default settings for dialog widgets

        # If this is a new installation
        if self.prefs == {}:
            self.prefs['input_source'] = 0
            self.prefs['conversion_type'] = 0
            self.prefs['input_locale'] = 0
            self.prefs['output_locale'] = 0
            self.prefs['use_target_phrases'] = True
            self.prefs['quotation_type'] = 0
            self.prefs['output_orientation'] = 0
            self.prefs['update_punctuation'] = False
            self.prefs['punc_omits'] = PUNC_OMITS
            # Write the preferences out to the JSON file
            self.prefs.commit()


        # Initialize the defaults. No need to commit since these are not
        # stored in the JSON file
        self.prefs.defaults['input_source'] = 0           # 0=whole book, 1=current file, 2=selected text

        self.prefs.defaults['conversion_type'] = 0        # 0=No change, 1=trad->simp, 2=simp->trad, 3=trad->trad
        self.prefs.defaults['input_locale'] = 0           # 0=Mainland, 1=Hong Kong, 2=Taiwan
        self.prefs.defaults['output_locale'] = 0          # 0=Mainland, 1=Hong Kong, 2=Taiwan
        self.prefs.defaults['use_target_phrases'] = True  # True/False

        self.prefs.defaults['quotation_type'] = 0         # 0=No change, 1=Western, 2=East Asian

        self.prefs.defaults['output_orientation'] = 0     # 0=No change, 1=Horizontal, 2=Vertical

        self.prefs.defaults['update_punctuation'] = False #  True/False

        self.prefs.defaults['punc_omits'] = PUNC_OMITS    # Horizontal mark string in horizontal/vertical
                                                          # dictionary pairs that is NOT to be used. No
                                                          # space between marks in string.

    def getCriteria(self):
        # Get the criteria from the current saved preferences if not passed in
        # The preference set is updated every time the user dialog is closed

        punc_dict = {}
        punc_regex = None

        if self.prefs['update_punctuation'] and (len(self.prefs['punc_omits']) != len(_h2v_master_dict.keys())):
            # create a dictionary without the keys contained in self.prefs['punc_omits']
            h2v = {}
            omit_set = set(self.prefs['punc_omits'])
            for key in _h2v_master_dict.keys():
                if not key in omit_set:
                    h2v[key] = _h2v_master_dict[key]

            # horizontal full width characters to their vertical presentation forms regex
            h2v_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, h2v.keys())))

            # vertical full width characters to their horizontal presentation forms regex
            v2h = {v: k for k, v in h2v.items()}
            v2h_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, v2h.keys())))

            if self.prefs['output_orientation'] == 1:
                punc_dict = v2h
                punc_regex = v2h_dict_regex
            elif self.prefs['output_orientation'] == 2:
                punc_dict = h2v
                punc_regex = h2v_dict_regex

        criteria = (
            self.prefs['input_source'], self.prefs['conversion_type'], self.prefs['input_locale'],
            self.prefs['output_locale'], self.prefs['use_target_phrases'], self.prefs['quotation_type'],
            self.prefs['output_orientation'], self.prefs['update_punctuation'], punc_dict, punc_regex)

        return criteria


def getPrefs():
    from calibre.utils.config import JSONConfig
    plugin_prefs = JSONConfig('plugins/{0}_ChineseConversion_settings'.format(PLUGIN_SAFE_NAME))

##    print('getPrefs preferences')
##    print(plugin_prefs['input_source'])           # 0=whole book, 1=current file, 2=selected text
##
##    print(plugin_prefs['conversion_type'])        # 0=No change, 1=trad->simp, 2=simp->trad, 3=trad->trad
##    print(plugin_prefs['input_locale'])           # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
##    print(plugin_prefs['output_locale'])          # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
##    print(plugin_prefs['use_target_phrases'])     # True/False
##
##    print(plugin_prefs['quotation_type'])         # 0=No change, 1=Western, 2=East Asian
##
##    print(plugin_prefs['output_orientation'])     # 0=No change, 1=Horizontal, 2=Vertical
##
##    print(plugin_prefs['update_punctuation'])     # True/False
##
##    print(plugin_prefs['punc_omits'])             # Horizontal mark string in horizontal/vertical
##                                                  # dictionary pairs that is NOT to be used. No
##                                                  # space between marks in string.
    return plugin_prefs


def get_language_code(criteria):
    """
    :param criteria: the description of the desired conversion
    :return: 'zh-CN', 'zh-TW', 'zh-HK', or 'None'
    """
    conversion_mode = criteria[CONVERSION_TYPE]
    input_type = criteria[INPUT_LOCALE]
    output_type = criteria[OUTPUT_LOCALE]

    # Return 'None' if Japan locale is used so that no language changes are made
    language_code = 'None'

    if conversion_mode == 1:
        #trad to simp
        if output_type == 0:
            language_code = 'zh-Hans-CN'

    elif conversion_mode == 2:
        #simp to trad, (we don't support Macau yet zh-MO)
        if output_type == 0:
            language_code = 'zh-Hant-CN'
        elif output_type == 1:
            language_code = 'zh-Hant-HK'
        else:
            language_code = 'zh-Hant-TW'

    elif conversion_mode == 3:
        #trad to trad, (we don't support Macau yet zh-MO)
        if input_type == 0:
            if output_type == 1:
                language_code = 'zh-Hant-HK'
            elif output_type == 2:
                language_code = 'zh-Hant-TW'
            else:
                #mainland trad -> mainland trad does nothing
                language_code = 'None'
        elif input_type == 1:
            if output_type == 0:
                language_code = 'zh-Hant-CN'
            else:
                #only TW trad -> mainland
                language_code = 'None'
        elif input_type == 2:
            if output_type == 0:
                language_code = 'zh-Hant-CN'
            else:
                #only HK trad -> mainland
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
    if language != "None":
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
        if(item.title != None):
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

def set_flow_direction(container, criteria, changed_files, converter):
    # Open OPF and set flow
    flow = 'default'
    if criteria[OUTPUT_ORIENTATION] == 2:
        flow = 'rtl'
    elif criteria[OUTPUT_ORIENTATION] == 1:
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
    if criteria[OUTPUT_ORIENTATION] == 1:
        orientation = 'horizontal-tb'
        orientation_azw3 = 'horizontal-lr'
        break_rule = 'auto'
    if criteria[OUTPUT_ORIENTATION] == 2:
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
    for name, mt in container.mime_map.items():
        if mt in OEB_STYLES:
            # Get the sheet as a python css_parser CSSStyleSheet object
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
        for name, mt in container.mime_map.items():
            if mt in OEB_STYLES:
                # Get the sheet as a python css_parser CSSStyleSheet object
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
        for name, mt in container.mime_map.items():
            if mt in OEB_STYLES:
                # Get the sheet as a python css_parser CSSStyleSheet object
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
    :return a tuple of the conversion direction and the output format:
      1) 'hk2s', 'hk2t', 'jp2t', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2hkp', 't2jp', 't2s', 't2tw', 'tw2s', 'tw2sp', 'tw2t', 'no_conversion', or 'unsupported_conversion'
    """
    conversion_mode = criteria[CONVERSION_TYPE]
    input_type = criteria[INPUT_LOCALE]
    output_type = criteria[OUTPUT_LOCALE]
    use_target_phrasing = criteria[USE_TARGET_PHRASES]

    configuration = 'unsupported_conversion'

    if conversion_mode == 0:
        #no conversion desired
        configuration = 'no_conversion'

    elif conversion_mode == 1:
        #trad to simp
        if input_type == 0:         # mainland
            if output_type == 0:    # mainland
                configuration = 't2s'
            elif output_type == 3:     # Japan
                configuration = 't2jp' # traditional Chinese hanzi to simplified modern Japanese kanji
            else: # HK or TW
                configuration = 'unsupported_conversion'
        elif input_type == 1:       # Hong Kong
            if output_type != 0:    # not mainland
                configuration = 'unsupported_conversion'
            else:
                configuration = 'hk2s'
        elif input_type == 2:       # Taiwan
            if output_type != 0:    # not mainland
                configuration = 'unsupported_conversion'
            else:
                configuration = 'tw2s'
                if use_target_phrasing:
                    configuration += 'p'
        else:
            # Japan is simplified kanji only
            configuration = 'unsupported_conversion'

    elif conversion_mode == 2:
        #simp to trad
        if input_type == 0:             #mainland
            if output_type == 0:        # mainland
                configuration = 's2t'
            elif output_type == 1:      # Hong Kong
                configuration = 's2hk'
            elif output_type == 2:       # Taiwan
                configuration = 's2tw'
                if use_target_phrasing:
                    configuration += 'p'
            else:
                # Japan
                configuration = 'unsupported_conversion'
        elif input_type == 3:          # Japan
            if output_type == 0:       # mainland
                configuration = 'jp2t' #Simplified modern Japanese kanji to traditional Chinese hanzi
            else:
                # HK or TW
                configuration = 'unsupported_conversion'
        else:
            # HK or TW are traditional only
            configuration = 'unsupported_conversion'

    else:
        #trad to trad
        if input_type == 0:             # mainland
            if output_type == 0:        # mainland
                configuration = 'no_conversion' # does nothing
            elif output_type == 1:        # Hong Kong
                configuration = 't2hk'
            elif output_type == 2:      # Taiwan
                configuration = 't2tw'
            else:                       # mainland
                # Japan is invalid
                configuration = 'unsupported_conversion'
        elif input_type == 1:           # Hong Kong
            if output_type == 0:
                configuration = 'hk2t'
            elif output_type == 1:        # Hong Kong
                configuration = 'no_conversion' # does nothing
            else:
                #HK trad -> TW trad not supported, Japan is invalid
                configuration = 'unsupported_conversion'
        elif input_type == 2:           # Taiwan
            if output_type == 0:
                configuration = 'tw2t'
            elif output_type == 2:        # Taiwan
                configuration = 'no_conversion' # does nothing
            else:
                #TW trad -> HK trad not supported, Japan is invalid
                configuration = 'unsupported_conversion'
        else:
            #JP is simplified kanji only
            configuration = 'unsupported_conversion'

    return configuration

def cli_get_criteria(args):
    #Note: criteria is a tuple of the form:
    #criteria = (
    #        process_single_file(BOOL), output_mode(INT), input_locale(INT),
    #        output_locale(INT), use_target_phrases(BOOL), quote_type(INT)),
    #        text_direction(INT)
    #   input_source:       0=whole book
    #                       1=current file
    #                       2=selected text
    #   output_mode:        0 = no change
    #                       1 = traditional->simplified
    #                       2 = simplified->traditional
    #                       3 = traditional->traditional
    #   input_locale:       0 = Mainland, 1 = Hong Kong, 2 = Taiwan 3 = Japan
    #   output_local:       0 = Mainland, 1 = Hong Kong, 2 = Taiwan 3 = Japan
    #   use_target_phrase:  True - Modify text to use words associated with target locale
    #   quote_type:         0 = No change, 1 = Western, 2 = East Asian
    #   text_direction:     0 = No change, 1 = Horizontal, 2 = Vertical
    #   update_punctuation  True - Modify punctuation to match text_direction

    # Set up default values
    input_source = 0            # Whole book
    output_mode = 0             # None
    input_locale = 0            # Mainland
    output_locale = 0           # Mainland
    use_target_phrase = False
    quote_type = 0              # No change
    text_direction = 0          # No change
    update_punctuation = False  # No change

    # Get some of the criteria from the current saved preferences or default value
    # The preference set is updated every time the user dialog is closed
    prefs = getPrefs()

    punc_dict = {}
    punc_regex = None
    omits = prefs.get('punc_omits', PUNC_OMITS)

    if args.punctuation_opt and (args.text_dir_opt != 'none') and (len(omits) != len(_h2v_master_dict.keys())):
        # copy the master conversion dictionary
        h2v = _h2v_master_dict

        # remove unwanted conversions; these are stored in prefs
        for x in omits:
            del h2v[x]
        h2v_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, h2v.keys())))

        # Vertical full width characters to their Horizontal presentation forms lookup
        v2h = {v: k for k, v in h2v.items()}
        v2h_dict_regex = re.compile("(%s)" % "|".join(map(re.escape, v2h.keys())))

        if args.text_dir_opt == 'h':
            punc_dict = v2h
            punc_regex = v2h_dict_regex
        elif args.text_dir_opt == 'v':
            punc_dict = h2v
            punc_regex = h2v_dict_regex

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
    elif args.orig_opt == 'jp':
        input_locale = 3

    if args.dest_opt == 'hk':
        output_locale = 1
    elif args.dest_opt == 'tw':
        output_locale = 2
    elif args.dest_opt == 'jp':
        output_locale = 3

    use_target_phrase = args.phrase_opt

    if args.quote_type_opt == 'w':
        quote_type = 1
    elif args.quote_type_opt == 'e':
        quote_type = 2

    if args.text_dir_opt == 'h':
        text_direction = 1
    elif args.text_dir_opt == 'v':
        text_direction = 2

    criteria = (
        input_source, output_mode, input_locale,
        output_locale, use_target_phrase, quote_type,
        text_direction, update_punctuation, punc_dict, punc_regex)

    return criteria

def cli_process_files(criteria, container, converter, parser):
    lang = get_language_code(criteria)
    if lang != "None":
        language = 'lang=\"' + lang + '\"'
        parser.setLanguageAttribute(language)
    else:
        parser.setLanguageAttribute(None)

    # Cover the entire book
    # Set metadata and Table of Contents (TOC)
    changed_files = []
    if criteria[CONVERSION_TYPE] != 0:
        set_metadata_toc(container, lang, criteria, changed_files, converter)

    # Set text orientation
    if criteria[OUTPUT_ORIENTATION] != 0:
        set_flow_direction(container, criteria, changed_files, converter)

    # Cover the text
    file_list = [i[0] for i in container.mime_map.items() if i[1] in OEB_DOCS]
    clean = True
    for name in file_list:
        data = container.raw_data(name)
        htmlstr = parser.processText(data, criteria)
        if htmlstr != data:
            container.dirty(name)
            container.open(name, 'w').write(htmlstr)
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
        print(_('Input locale: ') + args.orig_opt.upper())
        print(_('Output locale: ') + args.dest_opt.upper())
        print(_('Use destination phrases: ') + str(args.phrase_opt))

    print(_('Quotation Mark Style: '), end="")
    if args.quote_type_opt == 'no_change':
        print(_('No Change'))
    elif args.quote_type_opt == 'w':
        print(_('Western'))
    else:
        print(_('East Asian'))

    print(_('Text direction: '), end="")
    if args.text_dir_opt == 'no_change':
        print('No Change')
    elif args.text_dir_opt == 'h':
        print(_('Horizontal'))
        print(_('Update punctuation to match text direction: ') + str(args.punctuation_opt))
    else:
        print (_('Vertical'))
        print(_('Update punctuation to match text direction: ') + str(args.punctuation_opt))

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

    converter = OpenCC(get_resource_file)

    # Create the HTML parser and pass in the converter
    html_parser = HTML_TextProcessor(converter)

    criteria = None

    list_of_locales = ['cn', 'hk', 'tw', 'jp']
    list_of_directions = ['t2s', 's2t', 't2t', 'none']
    quotation_types = ['w', 'e', 'no_change']
    text_directions = ['h', 'v', 'no_change']

    parser = argparse.ArgumentParser(description=_('Convert Chinese characters between traditional/simplified types and/or change text style.\n'
                                                   'Generally run as: calibre-debug --run-plugin \"Chinese Text Conversion\" -- [options] ebook-filepath\n'
                                                   'Plugin Version: ') + str(plugin_version[0]) + '.' + str(plugin_version[1]) + '.' + str(plugin_version[2]))
    parser.add_argument('-il', '--input-locale', dest='orig_opt', default='cn',
                        help=_('Set to the ebook origin locale if known (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-ol', '--output-locale', dest='dest_opt', default='cn',
                        help=_('Set to the ebook target locale (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-d', '--direction', dest='direction_opt', default='none',
                        help=_('Set to the ebook conversion direction (Default: none)'), choices=list_of_directions)
    parser.add_argument('-p', '--phrase_convert', dest='phrase_opt', help=_('Convert phrases to target locale versions (Default: False)'),
                        action='store_true')

    parser.add_argument('-qt', '--quotation-type', dest='quote_type_opt', default='no_change',
                        help=_('Set to Western or East Asian (Default: no_change)'), choices=quotation_types)
    parser.add_argument('-td', '--text-direction', dest='text_dir_opt', default='no_change',
                        help=_('Set to the ebook origin locale if known (Default: no_change)'), choices=text_directions)

    parser.add_argument('-up', '--update_punctuation', dest='punctuation_opt', help=_('Update punctuation to match direction change (Default: False)'),
                        action='store_true')

    parser.add_argument('-v', '--verbose', dest='verbose_opt', help=_('Print out details as the conversion progresses (Default: False)'),
                        action='store_true')
    parser.add_argument('-t', '--test', dest='test_opt', help=_('Run conversion operations without saving results (Default: False)'),
                        action='store_true')
    parser.add_argument('-q', '--quiet', dest='quiet_opt', help=_('Do not print anything, ignore warnings - this option overrides the -s option (Default: False)'),
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
    if conversion == 'unsupported_conversion':
        if not args.quiet_opt:
            print_conversion_info(args, file_set, plugin_version, '??')
            print(_('The input/output/direction combination selected is not supported.\n Please use a different input/output/direction combination'))
        return(1)
    elif conversion == 'no_conversion':
        if args.verbose_opt and not args.quiet_opt:
            print(_('No hanzi conversion'))
        converter.set_conversion(conversion)
    else:
        if args.verbose_opt and not args.quiet_opt:
            print(_('Using opencc-python conversion configuration file: ') + conversion + '.json')
        converter.set_conversion(conversion)
##        converter.clear_counts()

    #Print out the conversion info
    if not args.quiet_opt:
        print_conversion_info(args, file_set, plugin_version, conversion + '.json')

    #If show option given, exit after displaying settings
    if args.show_opt:
        return(0)

    if (args.outdir_opt == None) and args.append_suffix_opt == '':
        if not args.force_opt:
            response = str(input(_('No output directory specified, original ebook file will be overwritten. Is this OK? [N] or Y: '))).lower().strip()
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
        changed_files = cli_process_files(criteria, container, converter, html_parser)
        if (len(changed_files) > 0) and not args.quiet_opt:
            print(_('Changed'))
            if args.verbose_opt:
                for changed_file_name in changed_files:
                    print('   ' + changed_file_name)
        else:
            if not args.quiet_opt:
                print(_('Unchanged - No file written'))
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

