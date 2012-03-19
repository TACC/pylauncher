info :
	@echo "make clean"

clean :
	rm -f launchtest.* launcher.log jobtest.oe*
	for j in `qstat | awk '/eijkhout/ {print $$1}' ` ; do \
	  qdel $$j ; \
	done
	for j in `ps | grep python | cut -f 1 -d ' '` ; do \
	  kill $$j ; \
	done

