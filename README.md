# AjMC NE corpus

This dataset consists of named entity-annotated historical commentaries in the field of Classics. The annotated entities feature a few domain-specific entity types such as works, material objects (e.g. manuscripts) and bibliographic references, in addition to more universal named entities like persons, locations, organizations and dates.

## Dataset profile

| <!-- -->    | <!-- -->    |
|-------------|-------------|
| **Document type**       | scholarly commentaries (19C) |
| **Languages**           | English, French,  German, Ancient Greek, Latin |
| **Annotation guidelines** |[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3585750.svg)](https://doi.org/10.5281/zenodo.3585750)|
| **Annotation tool**     | [INCEpTION](https://inception-project.github.io/) |
| **Original format and tagging scheme** |`HIPE TSV format, IOB` |
| **Annotations**          | NERC, EL (towards Wikidata) |
| **Version**   | `v0.4` |
| **Related publication**               |[A Named Entity-Annotated Corpus of 19<sup>th</sup> Century Classical Commentaries](http://dx.doi.org/10.5334/johd.150)|
| **License** | [![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC_BY--NC--SA_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)|

## Entity tagset

List of annotated entities (coarse level):
- Person\* (`pers`)
- Location (`loc`)
- Organisation (`org`)
- Date (`date`)
- Work\* (`work`)
- Scope (`scope`)
- Object\* (`object`)

Entities marked with an asterisk (\*) are further classified into sub-types. For example, a *person* entity can be: a) mythological entity (`pers.myth`), b) author (`pers.author`), c) editor (`pers.editor`) or d) other (`pers.other`). See the [annotation guidelines](./annotation-guidelines-classics-KEs.pdf) for the full list of entity sub-types.

## Format

This dataset comes in the CoNLL-like HIPE TSV format (for further details see the [HIPE 2020 Task Participation Guidelines](https://doi.org/10.5281/zenodo.3677171), p. 8). Sentence boundaries are indicated by the `EndOfLine` flag, contained in the `MISC` column, and correspond to manually identified linguistic sentences (see Guidelines, section 4). Hyphenated words were manually identified and re-composed (i.e. de-hyphenated).

Annotated data come in two flavours, corresponding to two different sets of tasks: 
1) *NER and EL*: data contains annotations of universal entities, both coarse and fine grained, as well as entity links. See [sample file (English)](v0.1/HIPE-2022-ajmc-v0.1-sample-en.tsv).
2) *Citation mining* (files with `_biblio` prefix in the name): data contains annotations of bibliographic references to both primary and secondary sources, according to the taxonomy described in the Annotation Guidelines section 2.3. 

**NB**: the two files are fully aligned, meaning that line *n* in both files will refer to the same annotated token. As such, information from both files can be combined together and used in multi-task learning scenarios. 

## Related resources

**Hucitlib Knowledge Base.** Commentators make abundant use of very concise abbreviations when referring e.g. to ancient authors (`pers.author`) and their works (`work.primlit`). Such abbreviations constitute a substantial challenge, especially for entity linking. An external resource that can be used in this respect is the [`hucitlib` knowledge base](https://hucitlib.readthedocs.io/) which is partially linked to Wikidata and provides abbreviations and variant names/titles for classical authors and their works.  

**Citation mining.** The dataset [*Annotated References in the Historiography on Venice: 19th–21st centuries*](http://doi.org/10.5334/johd.9), despite originating from a slightly different domain (i.e. history of Venice), contains annotations of primary and secondary bibliographic references. The guidelines according to which it was annotated are compatible with our guidelines for bibliographic entities.

## License

The digitized commentaries are available in the Internet Archive and released in the Public Domain. This annotated dataset is published under a [Creative Commons CC BY license (v. 4.0)](https://creativecommons.org/licenses/by/4.0/). 

## Acknowledgements

Data in this repository were produced in the context of the Ajax Multi-Commentary project, funded by the Swiss National Science Foundation under an Ambizione grant [PZ00P1\_186033](http://p3.snf.ch/project-186033).

Contributors: Carla Amaya (UNIL), Kevin Duc (UNIL), Sven Najem-Meyer (EPFL), Matteo Romanello (UNIL).
