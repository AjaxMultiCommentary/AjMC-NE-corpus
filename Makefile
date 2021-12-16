SHELL:=/bin/bash

SCHEMA?= data/preparation/TypeSystem.xml
DATA_DIR?=data/preparation
RELEASE_DIR?=data/release
VERSION?=v0.1
ASSIGNMENTS_TABLE=document-selection.tsv


#all: clean download export release

miniref: clean-miniref download-miniref export-miniref #release-sample

clean-miniref:
	rm -r $(DATA_DIR)/minireference/*/curated/*
	rm -r $(DATA_DIR)/minireference/*/tsv/*

download-miniref: download-miniref-en download-miniref-de 

download-miniref-%:
	python scripts/inception/download_curated.py --project-name=ajmc-miniref-$* --output-dir=$(DATA_DIR)/minireference/$*/curated/ 

export-miniref: export-miniref-de export-miniref-en 

export-miniref-%:
	python lib/convert_xmi2clef_format.py -i $(DATA_DIR)/minireference/$*/curated/ \
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