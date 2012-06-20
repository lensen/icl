#!/usr/bin/env python

from setuptools import setup

setup(name='icl',
      version='1.0',
      description='Python based commandline tool and libraries for Icinga',
      author='Jeffrey Lensen',
      author_email='jeffrey@hyves.nl',
      url='http://github.com/lensen',
      packages=['icinga'],
      scripts = ['bin/icl'],
      data_files=[ ('/etc/icinga', ['etc/icl.cfg']) ]
)

