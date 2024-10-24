%.html: %.md
	pandoc -s -t html5 $< > $@

tutorial.md: templates/tutorial.md
	python build_template.py $< > $@

all: tutorial.html
