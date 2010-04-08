from setuptools import setup, find_packages
import sys, os

version = '0.9.1'

setup(name='friendly_curl',
      version=version,
      description="A friendly interface to PyCURL.",
      long_description="""\
""",
      classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
      ], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='curl url http',
      author='Nick Pilon, Gavin Carothers',
      author_email='npilon@oreilly.com, gavin@oreilly.com',
      url='http://code.google.com/p/friendlycurl/',
      license='Apache 2',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
	    "pycurl>=7.16.4", "httplib2",
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
