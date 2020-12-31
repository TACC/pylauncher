info ::
	@echo
	@echo "================================================"
	@echo "This is the makefile for the pylauncher utility."
	@echo "Mostly this is just administrative stuff"
	@echo "that only works for the author of the utility."
	@echo
	@echo "For questions contact"
	@echo "Victor Eijkhout, eijkhout@tacc.utexas.edu"
	@echo "================================================"
	@echo
	@echo "make rules:"

info ::
	@echo "make docs : regenerate all documentation"
	@echo "make html,latexpdf,man : specific type only"
.PHONY: docs
html latexpdf man ::
	make doctype DOCTYPE=$@
docs:
	make doctype DOCTYPE=html
	make doctype DOCTYPE=latexpdf
	make doctype DOCTYPE=man
DOCTYPE = html
doctype:
	@export PYTHONPATH=`pwd`:$PYTHONPATH \
	&&export logdir=`pwd` \
	&& cd docs/rst \
	&& echo "making docs in ${DOCTYPE} format" \
	&& make ${DOCTYPE} 2>&1 | tee $$logdir/docs.log
	@case ${DOCTYPE} in \
	( html ) \
	  rm -rf docs/${DOCTYPE}  ; \
	  cp -r docs/rst/_build/${DOCTYPE} docs/${DOCTYPE} ;; \
	( man ) \
	  rm -rf docs/${DOCTYPE}  ; \
	  cp -r docs/rst/_build/${DOCTYPE} docs/${DOCTYPE} ;; \
	( latexpdf ) \
	  cp docs/rst/_build/latex/PyLauncher.pdf docs ;; \
	esac
clean ::
	@rm -f docs.log

info ::
	@echo "make bundle : make a tarfile"
bundle :
	cd .. ; \
	  cp -r pylauncher-bitbucket pylauncher ; \
	  rm -rf pylauncher/.hg ; \
	  tar fcz pylauncher.tar.gz pylauncher ; \
	  rm -rf pylauncher

info ::
	@echo "make upload : copy html docs to the TACC website"
upload :
	cp docs/launcher.pptx docs/PyLauncher.pdf ${HOME}/DropBox/Scicomp
	@for f in ` git status | awk '/modified:/ {print $$2}' ` ; do \
	  git add $$f ; \
	done

info ::
	@echo "make github"
.PHONY: github
GITDIR = ${HOME}/Projects/pylauncher/pylauncher-github-tacc
github : clean
	cp -rf * ${GITDIR}
	cd ${GITDIR} ; git add * ; git commit -m "pylauncher update" ; git push

info ::
	@echo "make unittests [VERBOSE=1 (default 0)]"
.PHONY: unittests
NOSE = nosetests-2.7
VERBOSE = 0
unittests :
	@${NOSE} \
	  ` case ${VERBOSE} in ( yes | y | 1 ) echo "--verbose" ;; esac` \
	  pylauncher.py

info ::
	@echo "make clean"
clean ::
	@/bin/rm -rf *~ *.pyc __pycache__ \
	  pylauncher_tmp* *expire* queuestate* unittestlines \
	  docs/rst/_build docs/rst/*~
	cd examples ; make clean
	cd tutorial ; make clean
