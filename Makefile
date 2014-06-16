PACKAGE_BUCKET_NAME ?= packages.example.com

PROJECT_NAME ?= s3yum-updater
SPEC ?= $(PROJECT_NAME).spec
SOURCES := ./*.{py,init,md} ./LICENSE

RPMDIR ?= $(CURDIR)/dist
BUILDDIR ?= $(CURDIR)/build
DEFINES = \
	--define '_topdir $(CURDIR)' \
	--define '_rpmtopdir $(CURDIR)' \
	--define '_specdir $(CURDIR)' \
	--define '_rpmdir $(RPMDIR)' \
	--define '_srcrpmdir $(RPMDIR)' \
	--define '_sourcedir $(RPMDIR)' \
	--define '_builddir $(CURDIR)' \
	--define '_buildrootdir $(BUILDDIR)'

RPM_BUILDNAME := $(shell rpm --eval '%{_build_name_fmt}')
RPM ?= $(RPMDIR)/$(shell rpm --specfile $(SPEC) -q --qf '$(RPM_BUILDNAME)\n' $(DEFINES))

SOURCE0_URL ?= $(word 2, $(shell spectool -l -s 0 $(DEFINES) $(SPEC)))
SOURCE0 ?= $(RPMDIR)/$(shell basename $(SOURCE0_URL))

.PHONY: rpm install clean aws-resources

rpm: $(RPM)

install: $(RPM)
	sudo yum localinstall $<

clean:
	$(RM) -r $(SOURCE0) $(RPM) $(RPMDIR) $(BUILDDIR)

$(RPM): $(SPEC) $(SOURCE0)
	rpmbuild $(DEFINES) --clean -bb $<

$(SOURCE0): $(RPMDIR)
	tar -c --transform 's,^\.,$(PROJECT_NAME)-master,' -f $@ $(SOURCES)

$(RPMDIR):
	@mkdir $@

aws-resources: docs/cloudformation.json
	aws cloudformation create-stack --stack-name packages \
		--template-body "`cat $<`" \
		--capabilities CAPABILITY_IAM \
		--parameters "ParameterKey=PackageBucketName,ParameterValue=$(PACKAGE_BUCKET_NAME)"
