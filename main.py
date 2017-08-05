# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2016, Hopkins'

import re, os.path
from itertools import tee, islice, izip_longest

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
class TradSimpChinese(Tool):
    from calibre_plugins.chinese_text.resources.opencc_python.opencc import OpenCC
    converter = OpenCC()

    name = 'trad-simp-chinese'

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True
    
    zh_re = re.compile('lang=\"zh-\w+\"|lang=\"zh\"', re.IGNORECASE)

    # Create regular expressions to modify quote styles
    trad_to_simp_quotes = {'「':'＂', '」':'＂', '『':'＇', '』':'＇'}
    trad_to_simp_re = re.compile('|'.join(map(re.escape, trad_to_simp_quotes)))

    trad_to_simp_smart_quotes = {'「':'“', '」':'”', '『':'‘', '』':'’'}
    trad_to_simp_smart_re = re.compile('|'.join(map(re.escape, trad_to_simp_smart_quotes)))

    # Only change double quotes since a lone single quote might be used in an abbreviation
    simp_to_trad_quotes = {'“':'「', '”':'」'}
    simp_to_trad_re = re.compile('|'.join(map(re.escape, simp_to_trad_quotes)))    

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
                                _('No text meeting your criteria was found to change.'), show=True)

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
            # Set metadata and Table of Contents (TOC)
            self.filesChanged = self.filesChanged or set_metadata_toc(container, get_language_code(criteria), criteria, self.changed_files, self.converter)
            # Cover the text portion
            from calibre_plugins.chinese_text.resources.dialogs import ShowProgressDialog
            d = ShowProgressDialog(self.gui, container, OEB_DOCS, criteria, self.convert_text, _('Converting'))
            cancelled_msg = ''
            if d.wasCanceled():
                cancelled_msg = ' (cancelled)'
            self.filesChanged = self.filesChanged or (not d.clean)
            self.changed_files.extend(d.changed_files)

    def convert_text(self, data, criteria):
        from calibre_plugins.chinese_text.resources.utilities import tokenize
        if (criteria[5]):
            # update quotes was selected
            if (criteria[1] == 0):
                # traditional to simplified
                if (criteria[6]):
                    htmlstr_corrected = self.trad_to_simp_smart_re.sub(lambda match: self.trad_to_simp_smart_quotes[match.group(0)], data)
                else:
                    htmlstr_corrected = self.trad_to_simp_re.sub(lambda match: self.trad_to_simp_quotes[match.group(0)], data)
            elif (criteria[1] == 1):
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
                htmlstr_corrected = self.simp_to_trad_re.sub(lambda match: self.simp_to_trad_quotes[match.group(0)], htmlstrD)
            else:
                # traditional to traditional
                htmlstr_corrected = data
        else:
            htmlstr_corrected = data
        tokens = tokenize(htmlstr_corrected)
        result = []
        for cur_token in tokens:
            if cur_token[0] == "tag":
                # change language code inside of tags
                result.append(self.zh_re.sub(self.language, cur_token[1]))
            else:
                result.append(self.converter.convert(cur_token[1]))
        return "".join(result)

def get_language_code(criteria):
    """
    :param criteria: the description of the desired conversion
    :return: 'zh-CN', 'zh-TW', 'zh-HK', or 'None'
    """
    conversion_mode = criteria[1]
    input_type = criteria[2]
    output_type = criteria[3]
    use_target_phrasing = criteria[4]

    language_code = ''

    if conversion_mode == 0:
        #trad to simp, output type is always mainland (we don't yet support Malaysia/Singapore zh-SG)
        language_code = 'zh-CN'

    elif conversion_mode == 1:
        #simp to trad, (we don't support Macau yet zh-MO)
        if output_type == 0:
            language_code = 'zh-CN'
        elif output_type == 1:
            language_code = 'zh-HK'
        else:
            language_code = 'zh-TW'

    else:
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
    zh_re2 = re.compile('zh-\w+|zh', re.IGNORECASE)
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
    # Only update the dc language if the original language was a Chinese type
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

def get_configuration(criteria):
    """
    :param criteria: the description of the desired conversion
    :return: 'hk2s', 's2hk', 's2t', 's2tw', 's2twp', 't2hk', 't2s', 't2tw', 'tw2s', 'tw2sp', or 'None'
    """
    conversion_mode = criteria[1]
    input_type = criteria[2]
    output_type = criteria[3]
    use_target_phrasing = criteria[4]

    configuration = ''

    if conversion_mode == 0:
        #trad to simp, output type is always mainland
        if input_type == 0:
            configuration = 't2s'
        elif input_type == 1:
            configuration = 'hk2s'
        else:
            configuration = 'tw2s'
            if use_target_phrasing:
                configuration += 'p'

    elif conversion_mode == 1:
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

def cli_convert_text(data, language, converter):
    from calibre_plugins.chinese_text.resources.utilities import tokenize
    tokens = tokenize(data)
    result = []
    for cur_token in tokens:
        if cur_token[0] == "tag":
            # change language code inside of tags
            result.append(re.sub('lang=\"zh-\w+\"|lang=\"zh\"', 'lang=\"' + language + '\"', cur_token[1], flags=re.IGNORECASE))
        else:
            result.append(converter.convert(cur_token[1]))
    return "".join(result)

def cli_get_criteria(args):
    #Note: criteria is a tuple of the form:
    #criteria = (
    #        process_single_file(BOOL), output_mode(INT), input_locale(INT),
    #        output_locale(INT), use_target_phrases(BOOL))
    #   process_single_file:    True - In editor only process a selected file in epub
    #                           False - Process all files in epub
    #   output_mode:    0 = traditional->simplified
    #                   1 = simplified->traditional
    #                   2 = traditional->traditional
    #   input_locale:   0 = Mainland, 1 = Hong Kong, 2 = Taiwan
    #   output_local:   0 = Mainland, 1 = Hong Kong, 2 = Taiwan
    #   use_target_phrase:  True - Modify text to use words associated with target locale

    # Set up default values
    process_single_file = False
    output_mode = 0     # Traditional->Simplified 
    input_locale = 0    # Mainland
    output_locale = 0   # Mainland
    use_target_phrase = False  

    if args.direction_opt == 's2t':
        output_mode = 1
    elif args.direction_opt == 't2t':
        output_mode = 2

    if args.orig_opt == 'hk':
        input_locale = 1
    elif args.orig_opt == 'tw':
        input_locale = 2

    if args.dest_opt == 'hk':
        output_locale = 1
    elif args.dest_opt == 'tw':
        output_locale = 2
        
    use_target_phrase = args.phrase_opt
    
    criteria = (
        process_single_file, output_mode, input_locale,
        output_locale, use_target_phrase)
    return criteria

def cli_process_files(criteria, container, converter):
    from hashlib import md5
    lang = get_language_code(criteria)

    # Cover the entire book
    # Set metadata and Table of Contents (TOC)
    changed_files = []
    set_metadata_toc(container, lang, criteria, changed_files, converter)
    # Cover the text
    file_list = [i[0] for i in container.mime_map.items() if i[1] in OEB_DOCS]
    clean = True
    for name in file_list:
        data = container.raw_data(name)
        orig_hash = md5(data).digest()
        htmlstr = cli_convert_text(data, lang, converter)
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
    print(_('Configuration file: '), configuration_filename)
    print(_('Output direction: '), end="")
    if args.direction_opt == 't2s':
        print(_('Traditional->Simplified'))
    elif args.direction_opt == 's2t':
        print(_('Simplified->Traditional'))
    else:
        print(_('Traditional->Traditional'))
    print(_('Chinese input locale: ') + args.orig_opt.upper())
    print(_('Chinese output locale: ') + args.dest_opt.upper())
    print(_('Use destination phrases: ') + str(args.phrase_opt))
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
    list_of_directions = ['t2s', 's2t', 't2t']
    parser = argparse.ArgumentParser(description=_('Convert Chinese characters between traditional (t) and simplified (s) types.\nPlugin Version: ') +
                                     str(plugin_version[0]) + '.' + str(plugin_version[1]) + '.' + str(plugin_version[2]))
    parser.add_argument('-il', '--input-locale', dest='orig_opt', default='cn',
                        help=_('Set to the epub origin locale if known (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-ol', '--output-locale', dest='dest_opt', default='cn',
                        help=_('Set to the epub target locale (Default: cn)'), choices=list_of_locales)
    parser.add_argument('-d', '--direction', dest='direction_opt', default='t2s',
                        help=_('Set to the epub conversion direction (Default: t2s)'), choices=list_of_directions)
    parser.add_argument('-p', '--phrase_convert', dest='phrase_opt', help=_('Convert phrases to target locale versions (Default: False)'),
                        action='store_true')
    parser.add_argument('-v', '--verbose', dest='verbose_opt', help=_('Print out details as the conversion progresses (Default: False)'),
                        action='store_true')
    parser.add_argument('-t', '--test', dest='test_opt', help=_('Run conversion operations without saving results (Default: False)'),
                        action='store_true')
    parser.add_argument('-q', '--quiet', dest='quiet_opt', help=_('Do not print anything, ignore warnings - this option overides the -s option (Default: False)'),
                        action='store_true')
    parser.add_argument('-od', '--output-dir', dest='outdir_opt',
                        help=_('Set to the epub output file directory (Default: overwrite existing epub file)'))
    parser.add_argument('-a', '--append_suffix', dest='append_suffix_opt', default='',
                        help=_('Append a suffix to the output file basename (Default: '')'))
    parser.add_argument('-f', '--force', dest='force_opt', help=_('Force processing by ignoring warnings (e.g. allow overwriting files with no prompt)'),
                        action='store_true')
    parser.add_argument('-s', '--show', dest='show_opt', help=_('Show the settings based on user cmdline options and exit (Default: False)'),
                        action='store_true')
    parser.add_argument('epubFiles', metavar='epub-filepath', nargs='+',
                        help=_('One or more EPUB filepaths - UNIX style wildcards accepted'))

    args = parser.parse_args(argv)
    
    #Pull out the list of epubs
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
        
    for filespec in args.epubFiles:
        #Get a list of files
        file_list = glob.glob(filespec)
        for filename in file_list:
            #Discard any non-files
            if not os.path.isfile(filename):
                if not args.quiet_opt:
                    print(_('Discarding - Not a file: ') + filename)
                continue
            #Discard any files not ending in epub
            if not filename.lower().endswith(".epub"):
                if not args.quiet_opt:
                    print(_('Discarding - Does not end in \'.epub\': ') + filename)
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
    else:
        if args.verbose_opt and not args.quiet_opt:
            print(_('Using opancc-python conversion configuration file: ') + conversion + '.json')
        converter.set_conversion(conversion)

    #Print out the conversion info
    if not args.quiet_opt:
        print_conversion_info(args, file_set, plugin_version, conversion + '.json')

    #If show option given, exit after displaying settings
    if args.show_opt:
        return(0)

    if (args.outdir_opt == None) and args.append_suffix_opt == '':
        if not args.force_opt:
            response = str(raw_input(_('No output directory specified, original epub file will be overwritten. Is this OK? [N] or Y: '))).lower().strip()
            if (len(response)) > 0 and (response[0] == 'y'):
                pass
            else:
                print(_('Exiting without changes'))
                return(0)

    if len(file_set) == 0:
        if not args.quiet_opt:
            print(_('No epub files specified!'))
            return(0)

    #Loop through the filenames
    for filename in file_set:
        #Print out the current operation
        if not args.quiet_opt:
            print(_('Converting epub: ') + os.path.basename(filename + ' .... '), end="")
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
        #if changes, save the container as an epub file with a name based on the conversion criteria
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
                #Create absolute path to filename. Earlier code already verified that it ends in '.epub'
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

