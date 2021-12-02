SHELL:=/bin/bash

SCHEMA?= data/preparation/xmi/TypeSystem.xml
DATA_DIR?=data/preparation
RELEASE_DIR?=data/release
VERSION?=v0.3


all: clean download export release

clean:
	rm -r $(DATA_DIR)/xmi/*
	rm -r $(DATA_DIR)/tsv/*

download: download-epibau_band_1-revised download-epibau_band_2.1-revised download-epibau_band_2.2-revised download-epibau_band_3-revised
#download: download-epibau_band_1 download-epibau_band_2.1 download-epibau_band_2.2 download-epibau_band_3

download-%:
	python scripts/inception/download_curated.py --project-name=$* --output-dir=$(DATA_DIR)/xmi

#export: export-epibau_band_1 export-epibau_band_2.1 export-epibau_band_2.2 export-epibau_band_3
export: export-epibau_band_1-revised export-epibau_band_2.1-revised export-epibau_band_2.2-revised export-epibau_band_3-revised

export-%:
	python lib/convert_xmi2clef_format.py -i $(DATA_DIR)/xmi/$*/ \
	-o $(DATA_DIR)/tsv/$*/ \
	-s $(SCHEMA) \
	-l $(DATA_DIR)/logs/export-annotated-$*.log \

release:
	python lib/create_datasets.py \
	--log-file=$(DATA_DIR)/logs/release-$*.log \
	--input-dir=$(DATA_DIR) \
	--output-dir=data/release/ \
	--data-version=$(VERSION)