SVGs:=$(shell ls *.svg)
SVGPDFs:=$(SVGs:%.svg=%.pdf)

all : $(SVGPDFs)

%.pdf : %.svg
	inkscape -A $@ -w 900 $<
