# AjMC NE corpus

## Data selection

- for each commentary, only the portion of a page marked as `introduction`, `preface` and `commentary` are kept
- pages that contain < 100 tokens are not considered for annotation 

## Compile and release dataset

Run

    make all

which is equivalent to

    make clean download export release