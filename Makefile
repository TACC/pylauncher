info :
	@echo "make tgz"

EXPORTDIR=pylauncher
tgz :
	@if [ `whoami` = "eijkhout" ] ; then \
	  echo "only to be done on clusters" ; exit 1 ; fi 
	rm -rf ../${EXPORTDIR} ; svn export . ../${EXPORTDIR}
	cd .. ; rm -rf pylauncher.tgz ; tar fcz pylauncher.tgz ${EXPORTDIR}
