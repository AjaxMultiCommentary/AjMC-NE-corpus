SHELL:=/bin/bash

DATA_DIR?=data/preparation
RELEASE_DIR?=data/release
DATA_VERSION?=v0.4
ASSIGNMENTS_TABLE=document-selection.tsv
SCHEMA?= data/preparation/TypeSystem.xml

##########################################
# Make commands for full corpus release  #
##########################################


corpus: corpus-en corpus-de corpus-fr release-corpus-all

corpus-en: download-corpus-en retokenize-corpus-en convert-corpus-en

corpus-fr: download-corpus-fr retokenize-corpus-fr convert-corpus-fr

corpus-de: download-corpus-de retokenize-corpus-de convert-corpus-de

retokenize-corpus: retokenize-corpus-fr retokenize-corpus-de retokenize-corpus-en 

download-corpus-%:
	python scripts/inception/download_curated.py --project-name=ajmc-corpus-$* --output-dir=$(DATA_DIR)/corpus/$*/curated/
	python scripts/inception/download_curated.py --project-name=ajmc-miniref-$* --output-dir=$(DATA_DIR)/corpus/$*/curated/
	python scripts/inception/download_curated.py --project-name=ajmc-doubleannot-$* --output-dir=$(DATA_DIR)/corpus/$*/curated/

retokenize-corpus-%: 
	python lib/retokenization.py -i $(DATA_DIR)/corpus/$*/curated/ \
	-o $(DATA_DIR)/corpus/$*/retokenized/ -s $(SCHEMA) \
	-l data/preparation/logs/retokenization-corpus-$*.log

convert-corpus-%:
	python lib/convert_xmi2clef_format.py -i $(DATA_DIR)/corpus/$*/retokenized/ \
	-o $(DATA_DIR)/corpus/$*/tsv/ \
	-s $(SCHEMA) \
	-l $(DATA_DIR)/logs/export-annotated-corpus-$*.log \

release-corpus-%:
	@$(eval SET=$(shell if [ "miniref" == $* ]; then echo sample; else echo all ; fi))
	python lib/create_datasets.py \
	--set=$(SET) \
	--log-file=$(DATA_DIR)/logs/release-$*.log \
	--input-dir=$(DATA_DIR) \
	--output-dir=data/release/ \
	--data-version=$(DATA_VERSION) \
	--assignments-table=$(ASSIGNMENTS_TABLE)

# The part of this Makefile related to the HIPE-2022 data release was removed,
# but it can be found in earlier GH releases. 