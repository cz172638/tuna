VERSION := $(shell rpm -q --qf '%{VERSION}' --specfile rpm/SPECS/tuna.spec)

bz2:
	git archive --format=tar HEAD | bzip2 -9 > rpm/SOURCES/tuna-$(VERSION).tar.bz2

rpm: bz2
	rpmbuild -bb --define "_topdir $(PWD)/rpm" rpm/SPECS/tuna.spec
