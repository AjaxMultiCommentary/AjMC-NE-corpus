# AjMC NE corpus

This dataset consists of named entity-annotated historical commentaries in the field of Classics. The annotated Knowledge Entities (KEs) feature a few domain-specific entity types such as works, material objects (e.g. manuscripts) and bibliographic references, in addition to more universal named entities like persons, locations, organizations and dates.

## Dataset profile

| <!-- -->    | <!-- -->    |
|-------------|-------------|
| **Original dataset**    | TODO: add DOI |
| **Document type**       | scholarly commentaries (19C) |
| **Languages**           | English, French,  German, Ancient Greek, Latin |
| **Annotation guidelines** |[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3585750.svg)](https://doi.org/10.5281/zenodo.3585750)|
| **Annotation tool**     | [INCEpTION](https://inception-project.github.io/) |
| **Original format and tagging scheme** |`.conllp, IOB` |
| **Annotations**          | NERC, EL (towards Wikidata) |
| **Version**   | `v0.4` |
| **Related publication**               |TBD|
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
2) *Citation mining*: data contains annotations of bibliographic references to both primary and secondary sources, according to the taxonomy described in the Annotation Guidelines section 2.3. See [sample file (English)](v0.1/HIPE-2022-ajmc_biblio-v0.1-sample-en.tsv).

**NB**: the two files are fully aligned, meaning that line *n* in both files will refer to the same annotated token. As such, information from both files can be combined together and used in multi-task learning scenarios. 

## Statistics

Not available yet. 

## License

The digitized commentaries are available in the Internet Archive and released in the Public Domain. This annotated dataset is published under a [Creative Commons CC BY license (v. 4.0)](https://creativecommons.org/licenses/by/4.0/). 

## Domain specificity

This dataset raises some challenges for NER and EL that are related to its domain-specific nature: 

- *data sparsity*: the fact that some entity types are under-represented in this dataset (e.g. `date`) calls for approaches to deal with data sparsity (e.g. data augmentation, meta-learning);
- *dependance on context*: the overall context of a commentary has a direct impact on how entity mentions are crafted, especially in terms of conciseness of the referents. This is especially relevant for EL as capturing the global document context becomes essential to select the correct linking candidate. To give a concrete example, a scholar commenting on a tragedy by Sophocles will probably omit the ancient author's name when referring to other works by Sophocles. To refer to a line of Sophocles' play *Philoctetes* she may write "*Ph.* 100" instead of the more easily intelligible "Soph. *Philoct.* 110".

## Related resources

**Hucitlib Knowledge Base.** Commentators make abundant use of very concise abbreviations when referring e.g. to ancient authors (`pers.author`) and their works (`work.primlit`). Such abbreviations constitute a substantial challenge, especially for entity linking. An external resource that can be used in this respect is the [`hucitlib` knowledge base](https://hucitlib.readthedocs.io/) which is partially linked to Wikidata and provides abbreviations and variant names/titles for classical authors and their works.  

**Citation mining.** The dataset [*Annotated References in the Historiography on Venice: 19th–21st centuries*](http://doi.org/10.5334/johd.9), despite originating from a slightly different domain (i.e. history of Venice), contains annotations of primary and secondary bibliographic references. The guidelines according to which it was annotated are compatible with our guidelines for bibliographic entities.