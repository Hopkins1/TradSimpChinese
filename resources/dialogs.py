
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

"""
----------------------------
NOTE:
The "ShowProgressDialog" and ResultsDialog classes given below were
taken from the file "dialogs.py" which was part of the Calibre plugin
"diaps_toolbag" authored by DiapDealer.
----------------------------
"""

__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'

import os

try:
    from PyQt5.Qt import (Qt, QVBoxLayout, QApplication,
                      QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QListWidget, QTimer, QDialog)
except ImportError:
    from PyQt4.Qt import (Qt, QVBoxLayout, QApplication,
                      QDialogButtonBox, QHBoxLayout,
                      QProgressDialog, QListWidget, QTimer, QDialog)

from calibre.gui2 import error_dialog, choose_files, open_url
from calibre.utils.config import config_dir

from calibre.gui2.tweak_book.widgets import Dialog
from calibre_plugins.chinese_text.__init__ import (PLUGIN_NAME, PLUGIN_SAFE_NAME)


class ShowProgressDialog(QProgressDialog):
    def __init__(self, gui, container, match_list, criteria, callback_fn, action_type='Checking'):
        self.file_list = [i[0] for i in container.mime_map.items() if i[1] in match_list]
        self.clean = True
        self.changed_files = []
        self.total_count = len(self.file_list)
        QProgressDialog.__init__(self, '', _('Cancel'), 0, self.total_count, gui)
        self.setMinimumWidth(500)
        self.container, self.criteria, self.callback_fn, self.action_type = container, criteria, callback_fn, action_type
        self.gui = gui
        self.setWindowTitle('{0}...'.format(self.action_type))
        self.i = 0
        QTimer.singleShot(0, self.do_action)
        self.exec_()

    def do_action(self):
        if self.wasCanceled():
            return self.do_close()
        if self.i >= self.total_count:
            return self.do_close()
        name = self.file_list[self.i]
        data = self.container.raw_data(name)
        self.i += 1

        self.setLabelText('{0}: {1}'.format(self.action_type, name))
        # Send the necessary data to the callback function in main.py.
        htmlstr = self.callback_fn(data, self.criteria)
        if htmlstr != data:
            self.container.open(name, 'w').write(htmlstr)
            self.container.dirty(name)
            self.changed_files.append(name)
            self.clean = False

        self.setValue(self.i)

        # Lather, rinse, repeat
        QTimer.singleShot(0, self.do_action)

    def do_close(self):
        self.hide()
        self.gui = None

class ResultsDialog(Dialog):
    def __init__(self, parent, files):
        self.files = files
        Dialog.__init__(self, _('Changed Files'), 'toolbag_show_results_dialog', parent)

    def setup_ui(self):
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        main_layout = QHBoxLayout()
        layout.addLayout(main_layout)
        self.listy = QListWidget()
        # self.listy.setSelectionMode(QAbstractItemView.ExtendedSelection)
        main_layout.addWidget(self.listy)
        self.listy.addItems(self.files)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box = QDialogButtonBox()

        ok_button = button_box.addButton(_("See what changed"), QDialogButtonBox.AcceptRole)
        cancel_button = button_box.addButton(_("Close"), QDialogButtonBox.RejectRole)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

