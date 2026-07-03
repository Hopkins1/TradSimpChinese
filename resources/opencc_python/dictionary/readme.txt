reverse.py
    for reversing dictionary keys and values (requires Python3)

    reverse 'JPVariants.txt' 'TWVariants.txt', 'HKVariants.txt'
    to 'JPVariantsRev.txt' 'TWVariantsRev.txt', 'HKVariantsRev.txt'

	In a command shell whose current working directory is the dictionary

    Run:
        python reverse.py
		
	or Run:
        calibre-debug reverse.py

extract_tofu_risk.py
    for extracting dictionary keys and values that are in the
    CJK Unified Ideographs Extension B (U+20000 to U+2A6DF)
    (requires Python3)

    TSCharacters.txt is split into TSCharacters.txt and TSCharactersExt.txt.
    The latter file contains the dictionary with the CJK Unified Ideographs
    Extension B values.

	In a command shell whose current working directory is the dictionary

    Run:
        python extract_tofu_risk.py TSCharacters.txt TSCharactersExt.txt
		
	or Run:
        calibre-debug extract_tofu_risk.py TSCharacters.txt TSCharactersExt.txt
