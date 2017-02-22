from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

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
        'License :: Other/Proprietary License',
        'Operating System :: POSIX :: Linux',
        'Topic :: Communications :: Internet Phone',
        'Topic :: Communications :: Telephony',
        'Topic :: Office/Business'
    ],
    author='Anton Trishenkov',
    author_email='anton.trishenkov@gmail.com',
    url='',  # FIXME: set project repository
    license='MIT',
    packages=[
        'aiorestframework',
    ],
    zip_safe=True,
    install_requires=[
        'aiohttp==1.3.3',
        'trafaret>=0.7.5',
        'trafaret_config>=1.0.1',
        'watchdog>=0.8.3',
    ],
)
