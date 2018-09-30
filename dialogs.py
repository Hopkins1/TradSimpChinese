# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'

import os

try:
    from PyQt5.Qt import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                      QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QSize, QDialog, QCheckBox, QSpinBox, QScrollArea, QWidget)
except ImportError:
    from PyQt4.Qt import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                      QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QSize, QDialog, QCheckBox, QSpinBox, QScrollArea, QWidget)

from calibre.utils.config import config_dir

from calibre.gui2.tweak_book.widgets import Dialog
from calibre_plugins.chinese_text.__init__ import (PLUGIN_NAME, PLUGIN_SAFE_NAME)

'''
ConversionDialog
The conversion dialog asks/displays the following:
    -Which direction of conversion is desired (i.e. Traditional->Simplified, Simplified->Traditional, or Traditional->Traditional)
    -If converting from Traditional, what country style is the source of the text (Hong Kong, Mainland, or Taiwan)
    -If converting to Traditional, what country style is desired (Hong Kong, Mainland, or Taiwan)
    -What text should be converted (the currently selected file or the entire book)

The chosen settings are saved between program starts.

Note: This code is based on the Calibre plugin Diap's Editing Toolbag
'''
class ConversionDialog(Dialog):
    def __init__(self, parent, force_entire_book=False):
        self.prefs = self.prefsPrep()
        self.parent = parent
        self.force_entire_book = force_entire_book
        self.criteria = None
        Dialog.__init__(self, _('Chinese Conversion'), 'chinese_conversion_dialog', parent)

    def setup_ui(self):
        self.quote_for_trad_target = _("Update quotes: ＂＂,＇＇ -> 「」,『』")
        self.quote_for_simp_target = _("Update quotes: 「」,『』 -> ＂＂,＇＇")

        # Create layout for entire dialog
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        #Create a scroll area for the top part of the dialog
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)

        # Create widget for all the contents of the dialog except the OK and Cancel buttons
        self.scrollContentWidget = QWidget(self.scrollArea)
        self.scrollArea.setWidget(self.scrollContentWidget)
        widgetLayout = QVBoxLayout(self.scrollContentWidget)

        # Add scrollArea to dialog
        layout.addWidget(self.scrollArea)
        
        self.operation_group_box = QGroupBox(_('Conversion Direction'))
        widgetLayout.addWidget(self.operation_group_box)
        operation_group_box_layout = QVBoxLayout()
        self.operation_group_box.setLayout(operation_group_box_layout)

        operation_group=QButtonGroup(self)
        self.no_conversion_button = QRadioButton(_('No Conversion'))
        operation_group.addButton(self.no_conversion_button)
        self.trad_to_simp_button = QRadioButton(_('Traditional to Simplified'))
        operation_group.addButton(self.trad_to_simp_button)
        self.simp_to_trad_button = QRadioButton(_('Simplified to Traditional'))
        operation_group.addButton(self.simp_to_trad_button)
        self.trad_to_trad_button = QRadioButton(_('Traditional to Traditional'))
        operation_group.addButton(self.trad_to_trad_button)
        operation_group_box_layout.addWidget(self.no_conversion_button)
        operation_group_box_layout.addWidget(self.trad_to_simp_button)
        operation_group_box_layout.addWidget(self.simp_to_trad_button)
        operation_group_box_layout.addWidget(self.trad_to_trad_button)
        self.no_conversion_button.toggled.connect(self.update_gui)
        self.trad_to_simp_button.toggled.connect(self.update_gui)
        self.simp_to_trad_button.toggled.connect(self.update_gui)
        self.trad_to_trad_button.toggled.connect(self.update_gui)


        self.style_group_box = QGroupBox(_('Language Styles'))
        widgetLayout.addWidget(self.style_group_box)
        style_group_box_layout = QVBoxLayout()
        self.style_group_box.setLayout(style_group_box_layout)

        input_layout = QHBoxLayout()
        style_group_box_layout.addLayout(input_layout)
        self.input_region_label = QLabel(_('Input:'))
        input_layout.addWidget(self.input_region_label)
        self.input_combo = QComboBox()
        input_layout.addWidget(self.input_combo)
        self.input_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan')])
        self.input_combo.setToolTip(_('Select the origin region of the input'))
        self.input_combo.currentIndexChanged.connect(self.update_gui)

        output_layout = QHBoxLayout()
        style_group_box_layout.addLayout(output_layout)
        self.output_region_label = QLabel(_('Output:'))
        output_layout.addWidget(self.output_region_label)
        self.output_combo = QComboBox()
        output_layout.addWidget(self.output_combo)
        self.output_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan')])
        self.output_combo.setToolTip(_('Select the desired region of the output'))
        self.output_combo.currentIndexChanged.connect(self.update_gui)

        self.use_target_phrases = QCheckBox(_('Use output target phrases if possible'))
        self.use_target_phrases.setToolTip(_('Check to allow region specific word replacements if available'))
        style_group_box_layout.addWidget(self.use_target_phrases)
        self.use_target_phrases.stateChanged.connect(self.update_gui)

        self.quotation_group_box = QGroupBox(_('Quotation Marks'))
        widgetLayout.addWidget(self.quotation_group_box)
        quotation_group_box_layout = QVBoxLayout()
        self.quotation_group_box.setLayout(quotation_group_box_layout)

        quotation_group=QButtonGroup(self)
        self.quotation_no_conversion_button = QRadioButton(_('No Conversion'))
        quotation_group.addButton(self.quotation_no_conversion_button)
        self.quotation_trad_to_simp_button = QRadioButton(self.quote_for_simp_target)
        quotation_group.addButton(self.quotation_trad_to_simp_button)
        self.quotation_simp_to_trad_button = QRadioButton(self.quote_for_trad_target)
        quotation_group.addButton(self.quotation_simp_to_trad_button)
        quotation_group_box_layout.addWidget(self.quotation_no_conversion_button)
        quotation_group_box_layout.addWidget(self.quotation_simp_to_trad_button)
        quotation_group_box_layout.addWidget(self.quotation_trad_to_simp_button)
        self.quotation_no_conversion_button.toggled.connect(self.update_gui)
        self.quotation_trad_to_simp_button.toggled.connect(self.update_gui)
        self.quotation_simp_to_trad_button.toggled.connect(self.update_gui)
        self.use_smart_quotes = QCheckBox("""Use curved 'Smart" quotes if applicable""")
        self.use_smart_quotes.setToolTip(_('Use smart curved half-width quotes rather than straight full-width quotes'))
        quotation_group_box_layout.addWidget(self.use_smart_quotes)
        self.use_smart_quotes.stateChanged.connect(self.update_gui)


        self.other_group_box = QGroupBox(_('Other Changes'))
        widgetLayout.addWidget(self.other_group_box)
        other_group_box_layout = QVBoxLayout()
        self.other_group_box.setLayout(other_group_box_layout)

        text_dir_layout = QHBoxLayout()
        other_group_box_layout.addLayout(text_dir_layout)
        direction_label = QLabel(_('Text Direction:'))
        text_dir_layout.addWidget(direction_label)
        self.text_dir_combo = QComboBox()
        text_dir_layout.addWidget(self.text_dir_combo)
        self.text_dir_combo.addItems([_('No Conversion'), _('Horizontal'), _('Vertical')])
        self.text_dir_combo.setToolTip(_('Select the desired text orientation'))
        self.text_dir_combo.currentIndexChanged.connect(self.update_gui)


        self.optimization_group_box = QGroupBox(_('Reader Device Optimization'))
        other_group_box_layout.addWidget(self.optimization_group_box)
        optimization_group_box_layout = QVBoxLayout()
        self.optimization_group_box.setLayout(optimization_group_box_layout)
        
        punc_group=QButtonGroup(self)
        self.text_dir_punc_none_button = QRadioButton("""No presentation optimization""")
        optimization_group_box_layout.addWidget(self.text_dir_punc_none_button)
        self.text_dir_punc_button = QRadioButton("""Optimize presentation for Readium reader""")
        self.text_dir_punc_button.setToolTip(_('Use vert/horiz punctuation presentation forms for Chrome Readium Epub3 reader'))
        optimization_group_box_layout.addWidget(self.text_dir_punc_button)
        self.text_dir_punc_kindle_button = QRadioButton("""Optimize presentation for Kindle reader""")
        self.text_dir_punc_kindle_button.setToolTip(_('Use vert/horiz puncuation presentation forms for Kindle reader'))
        optimization_group_box_layout.addWidget(self.text_dir_punc_kindle_button)
        self.text_dir_punc_none_button.toggled.connect(self.update_gui)
        self.text_dir_punc_button.toggled.connect(self.update_gui)
        self.text_dir_punc_kindle_button.toggled.connect(self.update_gui)

        source_group=QButtonGroup(self)
        self.file_source_button = QRadioButton(_('Selected File Only'))
        self.book_source_button = QRadioButton(_('Entire eBook'))
        source_group.addButton(self.file_source_button)
        source_group.addButton(self.book_source_button)
        self.source_group_box = QGroupBox(_('Source'))
        if not self.force_entire_book:
            widgetLayout.addWidget(self.source_group_box)
            source_group_box_layout = QVBoxLayout()
            self.source_group_box.setLayout(source_group_box_layout)
            source_group_box_layout.addWidget(self.file_source_button)
            source_group_box_layout.addWidget(self.book_source_button)

        layout.addSpacing(10)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self._ok_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.input_combo.setCurrentIndex(self.prefs['input_format'])
        self.output_combo.setCurrentIndex(self.prefs['output_format'])
        self.no_conversion_button.setChecked(self.prefs['no_conversion'])
        self.trad_to_simp_button.setChecked(self.prefs['trad_to_simp'])
        self.simp_to_trad_button.setChecked(self.prefs['simp_to_trad'])
        self.trad_to_trad_button.setChecked(self.prefs['trad_to_trad'])
        if not self.force_entire_book:
            self.file_source_button.setChecked(self.prefs['use_html_file'])
            self.book_source_button.setChecked(self.prefs['use_entire_book'])
        else:
            self.file_source_button.setChecked(False)
            self.book_source_button.setChecked(True)

        self.quotation_no_conversion_button.setChecked(self.prefs['quote_no_conversion'])
        self.quotation_trad_to_simp_button.setChecked(self.prefs['quote_trad_to_simp'])
        self.quotation_simp_to_trad_button.setChecked(self.prefs['quote_simp_to_trad'])

        self.use_smart_quotes.setChecked(self.prefs['use_smart_quotes'])
        self.text_dir_combo.setCurrentIndex(self.prefs['orientation'])
        self.text_dir_punc_none_button.setChecked(self.prefs['no_optimization'])
        self.text_dir_punc_button.setChecked(self.prefs['readium_optimization'])
        self.text_dir_punc_kindle_button.setChecked(self.prefs['kindle_optimization'])
        self.update_gui()

    def update_gui(self):
        if (self.quotation_trad_to_simp_button.isChecked()):
            self.use_smart_quotes.setEnabled(True)
        else:
            self.use_smart_quotes.setEnabled(False)

        if self.text_dir_combo.currentIndex() == 0:
            self.optimization_group_box.setEnabled(False)
            self.text_dir_punc_none_button.setEnabled(False)
            self.text_dir_punc_button.setEnabled(False)
            self.text_dir_punc_kindle_button.setEnabled(False)
        else:
            self.optimization_group_box.setEnabled(True)
            self.text_dir_punc_none_button.setEnabled(True)
            self.text_dir_punc_button.setEnabled(True)
            self.text_dir_punc_kindle_button.setEnabled(True)
            
        if self.no_conversion_button.isChecked():
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(False)
            self.use_target_phrases.setEnabled(False)
            self.output_region_label.setEnabled(False)
            self.input_region_label.setEnabled(False)
            self.style_group_box.setEnabled(False)
            
        elif self.trad_to_simp_button.isChecked():
            self.input_combo.setEnabled(True)
            #only mainland output locale for simplified output
            self.output_combo.setCurrentIndex(0)
            self.output_combo.setEnabled(False)
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(False)
            self.input_region_label.setEnabled(True)
            self.style_group_box.setEnabled(True)
            
        elif self.simp_to_trad_button.isChecked():
            #only mainland input locale for simplified input
            self.input_combo.setCurrentIndex(0)
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(True)
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(False)
            self.style_group_box.setEnabled(True)
            
        elif self.trad_to_trad_button.isChecked():
            #Trad->Trad
            #currently only mainland input locale for Trad->Trad
            self.input_combo.setCurrentIndex(0)
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(True)
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(False)
            self.style_group_box.setEnabled(True)

        else:
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
            self.use_target_phrases.setEnabled(True)
            self.style_group_box.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(True)

    def _ok_clicked(self):
        output_mode = 0
        if self.trad_to_simp_button.isChecked():
            output_mode = 1    #trad -> simp
        if self.simp_to_trad_button.isChecked():
            output_mode = 2    #simp -> trad
        elif self.trad_to_trad_button.isChecked():
            output_mode = 3    #trad -> trad

        quote_mode = 0
        if self.quotation_trad_to_simp_button.isChecked():
            quote_mode = 1    #trad -> simp
        if self.quotation_simp_to_trad_button.isChecked():
            quote_mode = 2    #simp -> trad

        optimization_mode = 0
        if self.text_dir_punc_button.isChecked():
            optimization_mode = 1    #Readium
        if self.text_dir_punc_kindle_button.isChecked():
            optimization_mode = 2    #Kindle
 
        self.criteria = (
            self.file_source_button.isChecked(), output_mode, self.input_combo.currentIndex(),
            self.output_combo.currentIndex(), self.use_target_phrases.isChecked(), quote_mode,
            self.use_smart_quotes.isChecked(), self.text_dir_combo.currentIndex(), optimization_mode)
        self.savePrefs()
        self.accept()

    def getCriteria(self):
        return self.criteria

    def prefsPrep(self):
        from calibre.utils.config import JSONConfig
        plugin_prefs = JSONConfig('plugins/{0}_ChineseConversion_settings'.format(PLUGIN_SAFE_NAME))
        plugin_prefs.defaults['input_format'] = 0
        plugin_prefs.defaults['output_format'] = 0
        plugin_prefs.defaults['no_conversion'] = True
        plugin_prefs.defaults['trad_to_simp'] = False
        plugin_prefs.defaults['use_html_file'] = True
        plugin_prefs.defaults['simp_to_trad'] = False
        plugin_prefs.defaults['trad_to_trad'] = False
        plugin_prefs.defaults['use_entire_book'] = True
        plugin_prefs.defaults['use_target_phrases'] = True
        plugin_prefs.defaults['quote_no_conversion'] = True
        plugin_prefs.defaults['quote_trad_to_simp'] = False
        plugin_prefs.defaults['quote_simp_to_trad'] = False
        plugin_prefs.defaults['use_smart_quotes'] = False
        plugin_prefs.defaults['orientation'] = 0
        plugin_prefs.defaults['no_optimization'] = True
        plugin_prefs.defaults['readium_optimization'] = False
        plugin_prefs.defaults['kindle_optimization'] = False
        return plugin_prefs

    def savePrefs(self):
        self.prefs['input_format'] = self.input_combo.currentIndex()
        self.prefs['output_format'] = self.output_combo.currentIndex()
        self.prefs['no_conversion'] = self.no_conversion_button.isChecked()
        self.prefs['trad_to_simp'] = self.trad_to_simp_button.isChecked()
        self.prefs['use_html_file'] = self.file_source_button.isChecked()
        self.prefs['simp_to_trad'] = self.simp_to_trad_button.isChecked()
        self.prefs['trad_to_trad'] = self.trad_to_trad_button.isChecked()
        self.prefs['use_entire_book'] = self.book_source_button.isChecked()
        self.prefs['use_target_phrases'] = self.use_target_phrases.isChecked()
        self.prefs['quote_no_conversion'] = self.quotation_no_conversion_button.isChecked()
        self.prefs['quote_trad_to_simp'] = self.quotation_trad_to_simp_button.isChecked()
        self.prefs['quote_simp_to_trad'] = self.quotation_simp_to_trad_button.isChecked()        
        self.prefs['use_smart_quotes'] = self.use_smart_quotes.isChecked()
        self.prefs['orientation'] = self.text_dir_combo.currentIndex()
        self.prefs['no_optimization'] = self.text_dir_punc_none_button.isChecked()
        self.prefs['readium_optimization'] = self.text_dir_punc_button.isChecked()
        self.prefs['kindle_optimization'] = self.text_dir_punc_kindle_button.isChecked()

