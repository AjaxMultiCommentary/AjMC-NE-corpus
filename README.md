# EpiBau Corpus

Metadata about the corpus can be found [here](https://docs.google.com/spreadsheets/d/1_CWl76JoNt5kN-NkGlg5-p2Dl8me_LDPsK9rWiysQc0/edit#gid=0).

The folder [`data/sample`](./data/sample/) contains a sample of four chapters, manually corrected, with output as IOB and UIMA/XMI. See the [README file there](./data/sample/README.md) for more details.

## Compile and release dataset

Run

    make all

which is equivalent to

    make clean download export release