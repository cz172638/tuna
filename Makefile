PACKAGE := tuna
VERSION := $(shell rpm -q --qf '%{VERSION} ' --specfile rpm/SPECS/tuna.spec | cut -d' ' -f1)

rpmdirs:
	@[ -d rpm/BUILD ]   || mkdir rpm/BUILD
	@[ -d rpm/RPMS ]    || mkdir rpm/RPMS
	@[ -d rpm/SRPMS ]   || mkdir rpm/SRPMS
	@[ -d rpm/SOURCES ] || mkdir rpm/SOURCES

bz2: rpmdirs
	git archive --format=tar --prefix=$(PACKAGE)-$(VERSION)/ HEAD | \
	bzip2 -9 > rpm/SOURCES/$(PACKAGE)-$(VERSION).tar.bz2

rpm: bz2 rpmdirs
	rpmbuild -ba --define "_topdir $(PWD)/rpm" rpm/SPECS/$(PACKAGE).spec
