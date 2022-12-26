# -*- coding: utf-8 -*-

__license__   = 'GPL v3'

import os, re

try:
    from qt.core import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                  QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                  QProgressDialog, QSize, QDialog, QCheckBox, QSpinBox, QScrollArea, QWidget,
                  QPushButton)
except ImportError:
    from PyQt5.Qt import (Qt, QVBoxLayout, QLabel, QComboBox, QApplication, QSizePolicy,
                          QGroupBox, QButtonGroup, QRadioButton, QDialogButtonBox, QHBoxLayout,
                          QProgressDialog, QSize, QDialog, QCheckBox, QSpinBox, QScrollArea, QWidget,
                          QPushButton)

from calibre.utils.config import config_dir

from calibre.gui2.tweak_book.widgets import Dialog

'''
ConversionDialog
The conversion dialog asks/displays the following:
    -Which direction of conversion is desired (i.e. Traditional->Simplified, Simplified->Traditional, or Traditional->Traditional)
    -If converting from Traditional, what country style is the source of the text (Hong Kong, Mainland, or Taiwan)
    -If converting to Traditional, what country style is desired (Hong Kong, Mainland, or Taiwan)
    -What text should be converted (the currently entire book, current file or selected text)

The chosen settings are saved between program starts.

Note: This code is based on the Calibre plugin Diap's Editing Toolbag
'''


class ConversionDialog(Dialog):
    def __init__(self, parent, prefs, punc_dict, default_omitted_puncuation, force_entire_book=False):
        self.prefs = prefs
        self.parent = parent
        self.force_entire_book = force_entire_book
        Dialog.__init__(self, _('Chinese Conversion'), 'chinese_conversion_dialog', parent)
        self.punctuation_dialog = PuncuationDialog(self.parent, self.prefs, punc_dict, default_omitted_puncuation)


    def setup_ui(self):

##        print('Dialog preferences')
##        print(self.prefs['input_source'])           # 0=whole book, 1=current file, 2=selected text
##
##        print(self.prefs['conversion_type'])        # 0=No change, 1=trad->simp, 2=simp->trad, 3=trad->trad
##        print(self.prefs['input_locale'])           # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
##        print(self.prefs['output_locale'])          # 0=Mainland, 1=Hong Kong, 2=Taiwan 3=Japan
##        print(self.prefs['use_target_phrases'])     # True/False
##
##        print(self.prefs['quotation_type'])         # 0=No change, 1=Western, 2=East Asian
##
##        print(self.prefs['output_orientation'])     # 0=No change, 1=Horizontal, 2=Vertical
##
##        print(self.prefs['punc_omits'])             # Horizontal mark string in horizontal/vertical
##                                                    # dictionary pairs that is NOT to be used. No
##                                                    # space between marks in string.

        self.quote_for_trad_target = _("Update quotes: “ ”,‘ ’ -> 「 」,『 』")
        self.quote_for_simp_target = _("Update quotes: 「 」,『 』 -> “ ”,‘ ’")

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

        self.operation_group=QButtonGroup(self)
        self.no_conversion_button = QRadioButton(_('No Conversion'))
        self.operation_group.addButton(self.no_conversion_button)
        self.trad_to_simp_button = QRadioButton(_('Traditional to Simplified'))
        self.operation_group.addButton(self.trad_to_simp_button)
        self.simp_to_trad_button = QRadioButton(_('Simplified to Traditional'))
        self.operation_group.addButton(self.simp_to_trad_button)
        self.trad_to_trad_button = QRadioButton(_('Traditional to Traditional'))
        self.operation_group.addButton(self.trad_to_trad_button)
        operation_group_box_layout.addWidget(self.no_conversion_button)
        operation_group_box_layout.addWidget(self.trad_to_simp_button)
        operation_group_box_layout.addWidget(self.simp_to_trad_button)
        operation_group_box_layout.addWidget(self.trad_to_trad_button)
        self.operation_group.buttonClicked.connect(self.on_op_button_clicked)

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
        self.input_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan'), _('Japan')])
        self.input_combo.setToolTip(_('Select the origin region of the input'))
        self.input_combo.currentIndexChanged.connect(self.update_gui)

        output_layout = QHBoxLayout()
        style_group_box_layout.addLayout(output_layout)
        self.output_region_label = QLabel(_('Output:'))
        output_layout.addWidget(self.output_region_label)
        self.output_combo = QComboBox()
        output_layout.addWidget(self.output_combo)
        self.output_combo.addItems([_('Mainland'), _('Hong Kong'), _('Taiwan'), _('Japan')])
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
        self.text_dir_combo.currentIndexChanged.connect(self.direction_changed)

        punctuation_layout = QHBoxLayout()
        other_group_box_layout.addLayout(punctuation_layout)
        self.update_punctuation = QCheckBox(_('Update punctuation'))
        punctuation_layout.addWidget(self.update_punctuation)
        self.update_punctuation.stateChanged.connect(self.update_gui)
        self.punc_settings_btn = QPushButton()
        self.punc_settings_btn.setText("Settings...")

        punctuation_layout.addWidget(self.punc_settings_btn)
        self.punc_settings_btn.clicked.connect(self.punc_settings_btn_clicked)
        self.punctuation_dialog = None

        source_group=QButtonGroup(self)
        self.book_source_button = QRadioButton(_('Entire eBook'))
        self.file_source_button = QRadioButton(_('Current File'))
        self.seltext_source_button = QRadioButton(_('Selected Text in Current File'))
        self.seltext_source_button.setToolTip(_('“Selected Text” is bracketed by <!--PI_SELTEXT_START--> and <!--PI_SELTEXT_END-->'))
        source_group.addButton(self.book_source_button)
        source_group.addButton(self.file_source_button)
        source_group.addButton(self.seltext_source_button)
        self.source_group_box = QGroupBox(_('Source'))
        if not self.force_entire_book:
            widgetLayout.addWidget(self.source_group_box)
            source_group_box_layout = QVBoxLayout()
            self.source_group_box.setLayout(source_group_box_layout)
            source_group_box_layout.addWidget(self.book_source_button)
            source_group_box_layout.addWidget(self.file_source_button)
            source_group_box_layout.addWidget(self.seltext_source_button)

        layout.addSpacing(10)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self._ok_clicked)
        self.button_box.rejected.connect(self._reject_clicked)
        layout.addWidget(self.button_box)

        self.set_to_preferences()
        self.update_gui()

    def on_op_button_clicked(self, btn):
        self.block_signals(True)
        if btn == self.no_conversion_button:
            self.input_combo.setCurrentIndex(-1)  # blank out the entry
            self.output_combo.setCurrentIndex(-1) # blank out the entry
        else:
            self.input_combo.setCurrentIndex(0)   # mainland
            self.output_combo.setCurrentIndex(0)  # mainland
        self.block_signals(False)
        self.update_gui()

    def block_signals(self, state):
        # block or unblock the signals generated by these objects to avoid recursive calls
        self.input_combo.blockSignals(state)
        self.output_combo.blockSignals(state)
        self.no_conversion_button.blockSignals(state)
        self.trad_to_simp_button.blockSignals(state)
        self.simp_to_trad_button.blockSignals(state)
        self.trad_to_trad_button.blockSignals(state)
        self.file_source_button.blockSignals(state)
        self.seltext_source_button.blockSignals(state)
        self.book_source_button.blockSignals(state)
        self.quotation_trad_to_simp_button.blockSignals(state)
        self.quotation_simp_to_trad_button.blockSignals(state)
        self.quotation_no_conversion_button.blockSignals(state)
        self.text_dir_combo.blockSignals(state)
        self.update_punctuation.blockSignals(state)


    def set_to_preferences(self):
        # set the gui values to match those in the preferences
        self.block_signals(True)

        self.input_combo.setCurrentIndex(self.prefs['input_locale'])
        self.output_combo.setCurrentIndex(self.prefs['output_locale'])

        if self.prefs['conversion_type'] == 0:
            self.no_conversion_button.setChecked(True)
        elif self.prefs['conversion_type'] == 1:
            self.trad_to_simp_button.setChecked(True)
        elif self.prefs['conversion_type'] == 2:
            self.simp_to_trad_button.setChecked(True)
        else:
            self.trad_to_trad_button.setChecked(True)

        if not self.force_entire_book:
            if self.prefs['input_source'] == 1:
                self.file_source_button.setChecked(True)
            elif self.prefs['input_source'] == 2:
                self.seltext_source_button.setChecked(True)
            else:
                self.book_source_button.setChecked(True)
        else:
            self.book_source_button.setChecked(True)
            self.file_source_button.setChecked(False)
            self.seltext_source_button.setChecked(False)

        if self.prefs['quotation_type'] == 1:
            self.quotation_trad_to_simp_button.setChecked(True)
        elif self.prefs['quotation_type'] == 2:
            self.quotation_simp_to_trad_button.setChecked(True)
        else:
            self.quotation_no_conversion_button.setChecked(True)

        self.text_dir_combo.setCurrentIndex(self.prefs['output_orientation'])
        if self.text_dir_combo.currentIndex() == 0:
            self.update_punctuation.setChecked(False)
        else:
            self.update_punctuation.setChecked(self.prefs['update_punctuation'])

        self.block_signals(False)


    def direction_changed(self):
        # callback when text direction changes
        self.update_punctuation.blockSignals(True)
        self.punc_settings_btn.blockSignals(True)

        if self.text_dir_combo.currentIndex() == 0:    # no direction change
            self.update_punctuation.setChecked(False)
            self.update_punctuation.setEnabled(False)
            self.punc_settings_btn.setEnabled(False)

        else:
            self.update_punctuation.setChecked(True)
            self.update_punctuation.setEnabled(True)
            self.punc_settings_btn.setEnabled(True)

        self.punc_settings_btn.blockSignals(False)
        self.update_punctuation.blockSignals(False)

    def update_gui(self):
        # callback to update other gui items when one changes
        if self.no_conversion_button.isChecked():
            self.input_combo.setEnabled(False)
            self.output_combo.setEnabled(False)
            self.input_combo.setToolTip(_('Valid input/output combinations:\nNot Applicable'))
            self.output_combo.setToolTip(_('Valid input/output combinations:\nNot Applicable'))
            self.use_target_phrases.setEnabled(False)
            self.output_region_label.setEnabled(False)
            self.input_region_label.setEnabled(False)
            self.style_group_box.setEnabled(False)

        elif self.trad_to_simp_button.isChecked():
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(True)
            self.input_combo.setToolTip(_('Valid input/output combinations:\nHong Kong/Mainland\nMainland/Mainland\nTaiwan/Mainland\nMainland/Japan'))
            self.output_combo.setToolTip(_('Valid input/output combinations:\nHong Kong/Mainland\nMainland/Mainland\nTaiwan/Mainland\nMainland/Japan'))
            self.style_group_box.setEnabled(True)

        elif self.simp_to_trad_button.isChecked():
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
            self.input_combo.setToolTip(_('Valid input/output combinations:\nMainland/Hong Kong\nMainland/Mainland\nMainland/Taiwan\nJapan/Mainland'))
            self.output_combo.setToolTip(_('Valid input/output combinations:\nMainland/Hong Kong\nMainland/Mainland\nMainland/Taiwan\nJapan/Mainland'))
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(True)
            self.style_group_box.setEnabled(True)

        elif self.trad_to_trad_button.isChecked():
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
            self.input_combo.setToolTip(_('Valid input/output combinations:\nHong Kong/Mainland\nMainland/Hong Kong\nTaiwan/Mainland\nMainland/Taiwan\nMainland/Mainland\nHong Kong/Hong Kong\nTaiwan/Taiwan'))
            self.output_combo.setToolTip(_('Valid input/output combinations:\nHong Kong/Mainland\nMainland/Hong Kong\nTaiwan/Mainland\nMainland/Taiwan\nMainland/Mainland\nHong Kong/Hong Kong\nTaiwan/Taiwan'))
            self.use_target_phrases.setEnabled(True)
            self.output_region_label.setEnabled(True)
            self.input_region_label.setEnabled(True)
            self.style_group_box.setEnabled(True)

        if self.text_dir_combo.currentIndex() == 0:
            self.update_punctuation.blockSignals(True)
            self.update_punctuation.setChecked(False)
            self.update_punctuation.setEnabled(False)
            self.update_punctuation.blockSignals(False)
        else:
            self.update_punctuation.blockSignals(True)
            self.update_punctuation.setEnabled(True)
            self.update_punctuation.blockSignals(False)

        if self.update_punctuation.isChecked():
            self.punc_settings_btn.setEnabled(True)
        else:
            self.punc_settings_btn.setEnabled(False)


    def _ok_clicked(self):
        # save current settings into preferences and close dialog
        self.savePrefs()
        self.accept()


    def _reject_clicked(self):
        # restore initial settings and close dialog
        self.set_to_preferences()
        self.update_gui()
        self.reject()


    def punc_settings_btn_clicked(self):
        # open the punctuation dialog
        self.punctuation_dialog.exec_()


    def savePrefs(self):
        # save the current settings into the preferences
        self.prefs['input_locale'] = self.input_combo.currentIndex()
        self.prefs['output_locale'] = self.output_combo.currentIndex()

        if self.trad_to_simp_button.isChecked():
            self.prefs['conversion_type'] = 1
        elif self.simp_to_trad_button.isChecked():
            self.prefs['conversion_type'] = 2
        elif self.trad_to_trad_button.isChecked():
            self.prefs['conversion_type'] = 3
        else:
            self.prefs['conversion_type'] = 0

        if self.file_source_button.isChecked():
            self.prefs['input_source'] = 1
        elif self.seltext_source_button.isChecked():
            self.prefs['input_source'] = 2
        else:
            self.prefs['input_source'] = 0

        self.prefs['use_target_phrases'] = self.use_target_phrases.isChecked()

        if self.quotation_trad_to_simp_button.isChecked():
            self.prefs['quotation_type'] = 1
        elif self.quotation_simp_to_trad_button.isChecked():
            self.prefs['quotation_type'] = 2
        else:
            self.prefs['quotation_type'] = 0

        self.prefs['output_orientation'] = self.text_dir_combo.currentIndex()
        self.prefs['update_punctuation'] = self.update_punctuation.isChecked()


    def getRegex(self):
        # getter for the punctuation conversion regular expression object
        return self.punctuation_dialog.getRegex()


class PuncuationDialog(Dialog):

    def __init__(self, parent, prefs, punc_dict, default_omitted_puncuation):
        self.prefs = prefs
        self.punc_dict = punc_dict
        self.default_omitted_puncuation = default_omitted_puncuation
        self.parent = parent
        self.puncSettings = set()
        Dialog.__init__(self, _('Chinese Punctuation'), 'chinese_conversion_punctuation_dialog', parent)


    def setup_ui(self):
        self.punc_setting = {}
        self.checkbox_dict = {}

        # Create layout for entire dialog
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        #Create a scroll area for the top part of the dialog
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)

        # Create widget for all the contents of the dialog except the buttons
        self.scrollContentWidget = QWidget(self.scrollArea)
        self.scrollArea.setWidget(self.scrollContentWidget)
        widgetLayout = QVBoxLayout(self.scrollContentWidget)

        # Add scrollArea to dialog
        layout.addWidget(self.scrollArea)

        self.punctuation_group_box = QGroupBox(_('Punctuation'))
        widgetLayout.addWidget(self.punctuation_group_box)


        self.punctuation_group_box_layout = QVBoxLayout()
        self.punctuation_group_box.setLayout(self.punctuation_group_box_layout)

        for x in self.punc_dict:
            str = x + " <-> " + self.punc_dict[x]
            widget = QCheckBox(str)
            self.checkbox_dict[x] = widget
            self.punctuation_group_box_layout.addWidget(widget)
            if x in self.prefs['punc_omits']:
                widget.setChecked(False)
            else:
                widget.setChecked(True)


        self.button_box_settings = QDialogButtonBox()
        self.clearall_button = self.button_box_settings.addButton("Clear All", QDialogButtonBox.ActionRole)
        self.setall_button = self.button_box_settings.addButton("Set All", QDialogButtonBox.ActionRole)
        self.default_button = self.button_box_settings.addButton("Default", QDialogButtonBox.ActionRole)
        self.button_box_settings.clicked.connect(self._action_clicked)
        layout.addWidget(self.button_box_settings)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._ok_clicked)
        self.button_box.rejected.connect(self._reject_clicked)
        layout.addWidget(self.button_box)


    def savePrefs(self):
        setting = ""
        for x in self.puncSettings:
            setting = setting + x
        self.prefs['punc_omits'] = setting


    def _ok_clicked(self):
        self.puncSettings.clear()
        # Loop through and update set of unchecked items
        for x in self.checkbox_dict.keys():
            if not self.checkbox_dict[x].isChecked():
                self.puncSettings.add(x)
        self.savePrefs()
        self.accept()


    def _reject_clicked(self):
        # Restore back to values when first opened
        # This will be the same as the preferences
        ## loop through all checkboxes
        for x in self.checkbox_dict.keys():
            self.checkbox_dict[x].blockSignals(True)
            if x in self.prefs['punc_omits']:
                self.checkbox_dict[x].setChecked(False)
            else:
                self.checkbox_dict[x].setChecked(True)
            self.checkbox_dict[x].blockSignals(False)
        self.reject()


    def _action_clicked(self, button):
        ## Find out which button is pressed
        if button is self.clearall_button:
            ## loop through all checkboxes and unset
            for x in self.checkbox_dict.values():
                x.blockSignals(True)
                x.setChecked(False)
                x.blockSignals(False)

        elif button is self.setall_button:
            ## loop through all checkboxes and set
            for x in self.checkbox_dict.values():
                x.blockSignals(True)
                x.setChecked(True)
                x.blockSignals(False)

        elif button is self.default_button:
            ## loop through all checkboxes
            for x in self.checkbox_dict.keys():
                self.checkbox_dict[x].blockSignals(True)
                if x in self.default_omitted_puncuation:
                    self.checkbox_dict[x].setChecked(False)
                else:
                    self.checkbox_dict[x].setChecked(True)
                self.checkbox_dict[x].blockSignals(False)

