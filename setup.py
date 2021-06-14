#!/usr/bin/env python

from setuptools import setup, find_packages

__AUTHOR__ = 'QuantStack dev team'

setup(
    name='robotframework-interpreter',
    version='0.6.7',
    description='Utility functions for building a Robot Framework interpreter.',
    author=__AUTHOR__,
    maintainer=__AUTHOR__,
    url='https://github.com/martinRenou/robotframework-interpreter',
    license='BSD 3-Clause',
    keywords='robotframework interpreter',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=[
        'robotframework>=3.2,<5',
        'lunr',
        'Pillow',
        'pygments',
        'ipywidgets'
    ],
    extras_require={
        'testing': ['flake8'],
    },
    platforms=['any'],
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
