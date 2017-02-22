.PHONY: test
test:
	py.test --cov=aiorestframework

.PHONY: test-buildcov
test-buildcov:
	py.test --cov=aiorestframework && (echo "building coverage html, view at './htmlcov/index.html'"; coverage html)
