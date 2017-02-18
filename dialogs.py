# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'

import os

try:
    from PyQt5.Qt import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                      QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QSize, QDialog, QCheckBox)
except ImportError:
    from PyQt4.Qt import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                      QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QSize, QDialog, QCheckBox)

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

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.operation_group_box = QGroupBox(_('Conversion Direction'))
        layout.addWidget(self.operation_group_box)
        operation_group_box_layout = QVBoxLayout()
        self.operation_group_box.setLayout(operation_group_box_layout)

        operation_group=QButtonGroup(self)
        self.trad_to_simp_button = QRadioButton(_('Traditional to Simplified'))
        operation_group.addButton(self.trad_to_simp_button)
        self.simp_to_trad_button = QRadioButton(_('Simplified to Traditional'))
        operation_group.addButton(self.simp_to_trad_button)
        self.trad_to_trad_button = QRadioButton(_('Traditional to Traditional'))
        operation_group.addButton(self.trad_to_trad_button)
        operation_group_box_layout.addWidget(self.trad_to_simp_button)
        operation_group_box_layout.addWidget(self.simp_to_trad_button)
        operation_group_box_layout.addWidget(self.trad_to_trad_button)
        self.trad_to_simp_button.toggled.connect(self.update_gui)
        self.simp_to_trad_button.toggled.connect(self.update_gui)
        self.trad_to_trad_button.toggled.connect(self.update_gui)

        self.style_group_box = QGroupBox(_('Text Styles'))
        layout.addWidget(self.style_group_box)
        style_group_box_layout = QVBoxLayout()
        self.style_group_box.setLayout(style_group_box_layout)

        input_layout = QHBoxLayout()
        style_group_box_layout.addLayout(input_layout)
        label = QLabel(_('Input:'))
        input_layout.addWidget(label)
        self.input_combo = QComboBox()
        input_layout.addWidget(self.input_combo)
        self.input_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan')])
        self.input_combo.setToolTip(_('Select the origin region of the input'))
        self.input_combo.currentIndexChanged.connect(self.update_gui)

        output_layout = QHBoxLayout()
        style_group_box_layout.addLayout(output_layout)
        label = QLabel(_('Output:'))
        output_layout.addWidget(label)
        self.output_combo = QComboBox()
        output_layout.addWidget(self.output_combo)
        self.output_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan')])
        self.output_combo.setToolTip(_('Select the desired region of the output'))
        self.output_combo.currentIndexChanged.connect(self.update_gui)

        self.use_target_phrases = QCheckBox(_('Use output target phrases if possible'))
        self.use_target_phrases.setToolTip(_('Check to allow region specific word replacements if available'))
        style_group_box_layout.addWidget(self.use_target_phrases)
        self.use_target_phrases.stateChanged.connect(self.update_gui)

        self.use_correct_quotes = QCheckBox("")
        self.use_correct_quotes.setToolTip(_('Modify quotation marks in horizontal text to match region'))
        style_group_box_layout.addWidget(self.use_correct_quotes)
        self.use_correct_quotes.stateChanged.connect(self.update_gui)

        self.use_smart_quotes = QCheckBox("""Use curved 'Smart" quotes""")
        self.use_smart_quotes.setToolTip(_('Use smart curved half-width quotes rather than straight full-width quotes'))
        style_group_box_layout.addWidget(self.use_smart_quotes)
        self.use_smart_quotes.stateChanged.connect(self.update_gui)

        source_group=QButtonGroup(self)
        self.file_source_button = QRadioButton(_('Selected File Only'))
        self.book_source_button = QRadioButton(_('Entire eBook'))
        source_group.addButton(self.file_source_button)
        source_group.addButton(self.book_source_button)
        self.source_group_box = QGroupBox(_('Source'))
        if not self.force_entire_book:
            layout.addWidget(self.source_group_box)
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
        self.trad_to_simp_button.setChecked(self.prefs['trad_to_simp'])
        self.simp_to_trad_button.setChecked(self.prefs['simp_to_trad'])
        self.trad_to_trad_button.setChecked(self.prefs['trad_to_trad'])
        if not self.force_entire_book:
            self.file_source_button.setChecked(self.prefs['use_html_file'])
            self.book_source_button.setChecked(self.prefs['use_entire_book'])
        else:
            self.file_source_button.setChecked(False)
            self.book_source_button.setChecked(True)
        self.use_target_phrases.setChecked(self.prefs['use_target_phrases'])
        self.use_correct_quotes.setChecked(self.prefs['use_correct_quotes'])
        self.use_smart_quotes.setChecked(self.prefs['use_smart_quotes'])
        self.update_gui()

    def update_gui(self):
        if self.trad_to_simp_button.isChecked():
            self.input_combo.setEnabled(True)
            #only mainland output locale for simplified output
            self.output_combo.setCurrentIndex(0)
            self.output_combo.setEnabled(False)
            self.use_correct_quotes.setEnabled(True)
            self.use_correct_quotes.setText(self.quote_for_simp_target)
            if (self.use_correct_quotes.isChecked()):
                self.use_smart_quotes.setEnabled(True)
            else:
                self.use_smart_quotes.setEnabled(False)
            
        elif self.simp_to_trad_button.isChecked():
            #only mainland input locale for simplified input
            self.input_combo.setCurrentIndex(0)
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(True)
            self.use_correct_quotes.setEnabled(True)
            self.use_correct_quotes.setText(self.quote_for_trad_target)
            self.use_smart_quotes.setEnabled(False)
            
        elif self.trad_to_trad_button.isChecked():
            #Trad->Trad
            #currently only mainland input locale for Trad->Trad
            self.input_combo.setCurrentIndex(0)
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(True)
            self.use_correct_quotes.setEnabled(False)
            self.use_correct_quotes.setText(self.quote_for_trad_target)
            self.use_smart_quotes.setEnabled(False)
        else:
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
            self.use_correct_quotes.setEnabled(True)
            self.use_correct_quotes.setText(self.quote_for_simp_target)
            self.use_smart_quotes.setEnabled(False)

    def _ok_clicked(self):
        output_mode = 0        #trad -> simp
        if self.simp_to_trad_button.isChecked():
            output_mode = 1    #simp -> trad
        elif self.trad_to_trad_button.isChecked():
            output_mode = 2    #trad -> trad

        self.criteria = (
            self.file_source_button.isChecked(), output_mode, self.input_combo.currentIndex(),
            self.output_combo.currentIndex(), self.use_target_phrases.isChecked(),
            self.use_correct_quotes.isChecked(), self.use_smart_quotes.isChecked())
        self.savePrefs()
        self.accept()

    def getCriteria(self):
        return self.criteria

    def prefsPrep(self):
        from calibre.utils.config import JSONConfig
        plugin_prefs = JSONConfig('plugins/{0}_ChineseConversion_settings'.format(PLUGIN_SAFE_NAME))
        plugin_prefs.defaults['input_format'] = 0
        plugin_prefs.defaults['output_format'] = 0
        plugin_prefs.defaults['trad_to_simp'] = True
        plugin_prefs.defaults['use_html_file'] = True
        plugin_prefs.defaults['simp_to_trad'] = False
        plugin_prefs.defaults['trad_to_trad'] = False
        plugin_prefs.defaults['use_entire_book'] = False
        plugin_prefs.defaults['use_target_phrases'] = True
        plugin_prefs.defaults['use_correct_quotes'] = True
        plugin_prefs.defaults['use_smart_quotes'] = False
        return plugin_prefs

    def savePrefs(self):
        self.prefs['input_format'] = self.input_combo.currentIndex()
        self.prefs['output_format'] = self.output_combo.currentIndex()
        self.prefs['trad_to_simp'] = self.trad_to_simp_button.isChecked()
        self.prefs['use_html_file'] = self.file_source_button.isChecked()
        self.prefs['simp_to_trad'] = self.simp_to_trad_button.isChecked()
        self.prefs['trad_to_trad'] = self.trad_to_trad_button.isChecked()
        self.prefs['use_entire_book'] = self.book_source_button.isChecked()
        self.prefs['use_target_phrases'] = self.use_target_phrases.isChecked()
        self.prefs['use_correct_quotes'] = self.use_correct_quotes.isChecked()
        self.prefs['use_smart_quotes'] = self.use_smart_quotes.isChecked()


