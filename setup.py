from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup, find_packages

THIS_DIR = Path(__file__).resolve().parent
long_description = THIS_DIR.joinpath('README.rst').read_text()

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'aiorestframework/version.py').load_module()

package = THIS_DIR.joinpath('aiorestframework')

start_package_data = []


setup(
    name='aiorestframework',
    version=str(version.VERSION),
    description='REST Framework for aiohttp',
    long_description=long_description,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Framework :: Aiohttp'
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Telecommunications Industry',
        'License :: MIT',
        'Operating System :: POSIX :: Linux',
    ],
    author='Anton Trishenkov',
    author_email='anton.trishenkov@gmail.com',
    url='https://github.com/Skorpyon/aiorestframework',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    include_package_data=True,
    zip_safe=True,
    install_requires=[
        'ujson==1.35',
        'aiohttp>=2.0.7',
    ],
)
