merge.py
    for merging dictionary files into a single file

    merge 'TWPhrasesIT.txt', 'TWPhrasesName.txt', and 'TWPhrasesOther.txt'
    into a single file 'TWPhrases.txt'

	In a command shell whose current working directory is the dictionary
    
	Run:
        python merge.py
		
	or Run:
        calibre-debug merge.py

reverse.py
    for reversing dictionary keys and values (requires Python3)

    reverse 'TWVariants.txt', 'TWPhrases.txt', 'HKVariants.txt'
    to 'TWVariantsRev.txt', 'TWPhrasesRev.txt', 'HKVariantsRev.txt'

	In a command shell whose current working directory is the dictionary

    Run:
        python reverse.py
		
	or Run:
        calibre-debug reverse.py
