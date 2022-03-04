SHELL:=/bin/bash

SCHEMA?= data/preparation/TypeSystem.xml
DATA_DIR?=data/preparation
RELEASE_DIR?=data/release
HIPE_VERSION?=v2.0
ASSIGNMENTS_TABLE=document-selection.tsv

##########################################
# Make commands for full corpus release  #
##########################################


corpus: corpus-en release-corpus-all

corpus-en: download-corpus-en retokenize-corpus-en convert-corpus-en

corpus-fr: download-corpus-fr retokenize-corpus-fr convert-corpus-fr

corpus-de: download-corpus-de retokenize-corpus-de convert-corpus-de

download-corpus-%:
	python scripts/inception/download_curated.py --project-name=ajmc-corpus-$* --output-dir=$(DATA_DIR)/corpus/$*/curated/
	python scripts/inception/download_curated.py --project-name=ajmc-miniref-$* --output-dir=$(DATA_DIR)/corpus/$*/curated/

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
	--data-version=$(HIPE_VERSION) \
	--assignments-table=$(ASSIGNMENTS_TABLE)


##########################################
# Make commands for sample data release  #
##########################################

miniref: download-miniref retokenize-miniref export-miniref release-miniref

clear-miniref:
	rm -r $(DATA_DIR)/minireference/*/curated/*
	rm -r $(DATA_DIR)/minireference/*/retokenized/*
	rm -r $(DATA_DIR)/minireference/*/tsv/*

download-miniref: download-miniref-en download-miniref-de 

download-miniref-%:
	python scripts/inception/download_curated.py --project-name=ajmc-miniref-$* --output-dir=$(DATA_DIR)/minireference/$*/curated/ 

export-miniref: export-miniref-de export-miniref-en 

retokenize-miniref: retokenize-miniref-de retokenize-miniref-en

retokenize-miniref-%: 
	python lib/retokenization.py -i $(DATA_DIR)/minireference/$*/curated/ \
	-o $(DATA_DIR)/minireference/$*/retokenized/ -s $(SCHEMA) \
	-l data/preparation/logs/retokenization-miniref-$*.log

export-miniref-%:
	python lib/convert_xmi2clef_format.py -i $(DATA_DIR)/minireference/$*/retokenized/ \
	-o $(DATA_DIR)/minireference/$*/tsv/ \
	-s $(SCHEMA) \
	-l $(DATA_DIR)/logs/export-annotated-$*.log \

release-%:
	@$(eval SET=$(shell if [ "miniref" == $* ]; then echo sample; fi))
	python lib/create_datasets.py \
	--set=$(SET) \
	--log-file=$(DATA_DIR)/logs/release-$*.log \
	--input-dir=$(DATA_DIR) \
	--output-dir=data/release/ \
	--data-version=$(VERSION) \
	--assignments-table=$(ASSIGNMENTS_TABLE)