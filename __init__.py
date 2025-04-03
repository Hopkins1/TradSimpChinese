
__license__ = 'GPL 3'
__docformat__ = 'restructuredtext en'

from calibre.customize import EditBookToolPlugin

PLUGIN_NAME = "Chinese Text Conversion"
PLUGIN_SAFE_NAME = PLUGIN_NAME.strip().lower().replace(' ', '_')
PLUGIN_DESCRIPTION = 'A plugin to convert traditional and simplified Chinese text'
PLUGIN_VERSION_TUPLE = (3, 1, 0)
PLUGIN_VERSION = '.'.join([str(x) for x in PLUGIN_VERSION_TUPLE])
PLUGIN_AUTHORS = 'Hopkins'

class ChineseTextPlugin(EditBookToolPlugin):

    name = PLUGIN_NAME
    version = PLUGIN_VERSION_TUPLE
    author = PLUGIN_AUTHORS
    supported_platforms = ['windows', 'osx', 'linux']
    description = PLUGIN_DESCRIPTION
    minimum_calibre_version = (6, 0, 0)

    def cli_main(self,argv):
        #Typical Usage: calibre-debug --run-plugin "Chinese Text Conversion" -- -h
        from calibre_plugins.chinese_text.main import main as chinese_text_main
        chinese_text_main(argv[1:], self.version, usage='%prog --run-plugin '+'\"self.name\"'+' --')
